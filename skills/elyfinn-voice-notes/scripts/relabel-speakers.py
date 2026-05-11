#!/usr/bin/env python3
"""Interactively relabel speaker placeholders (e.g. `Speaker 1`, `[Speaker A]`,
`[说话人A]`) in a generated meeting note with real names.

Why: voice transcription pipelines label voices as anonymous `Speaker 1`,
`Speaker 2` (darknoon/audio-skills style) or `[Speaker A]`, `[Speaker B]`
(other pipelines) — consistent across the transcript but you can't tell
who's who. After the meeting note is generated, run this script to substitute
real names so the document is still readable months later.

Usage:
    python3 relabel-speakers.py meeting.md                       # interactive
    python3 relabel-speakers.py meeting.md --map 1=Alice,2=Bob   # batch (digit keys)
    python3 relabel-speakers.py meeting.md --map A=Alice,B=Bob   # batch (letter keys)
    python3 relabel-speakers.py meeting.md --no-backup --no-confirm --map 1=Alice

Recognized label formats:
    - `Speaker 1: ...`            ← darknoon/audio-skills default
    - `Speaker A: ...`            ← letter-keyed variants
    - `[Speaker A]: ...`          ← bracketed variants
    - `[说话人A]:` / `[与会者A]:` / `[发言人A]:`  ← Chinese-prefix variants
    - Bare references in prose like "Speaker 1 mentioned ..." or "说话人A 提到 ..."
"""

import argparse
import re
import shutil
import sys
from collections import OrderedDict
from pathlib import Path

# Each entry: (prefix, separator-between-prefix-and-key)
# `Speaker` is followed by a literal space, Chinese prefixes are directly
# adjacent to the key.
PREFIXES = [
    ("Speaker", " "),
    ("说话人", ""),
    ("与会者", ""),
    ("发言人", ""),
]

# Regex alternation that matches any prefix. The separator is encoded as
# `\s+` for English (tolerates multiple spaces) and empty for Chinese.
PREFIX_ALT = "(?:" + "|".join(
    re.escape(p) + (r"\s+" if sep else "") for p, sep in PREFIXES
) + ")"

# A key is one or more uppercase letters or digits (so we accept both
# letter-keyed labels like `Speaker A` / `Speaker AB` and numeric ones like
# `Speaker 1` / `Speaker 12`). `?` is also allowed for the rare case when
# the transcript marks an unclear speaker as `[Speaker ?]`.
KEY = r"[A-Z\d?]+"

# Match a transcript-style header line, e.g.:
#     [00:09:12] [Speaker A]: text     ← with timestamp + brackets
#     [Speaker A]: text                ← brackets only
#     Speaker 1: text                  ← darknoon style (no brackets, no timestamp)
TRANSCRIPT_LINE = re.compile(
    rf"""
    ^
    (?:\[(\d{{1,3}}:\d{{2}}(?::\d{{2}})?)\]\s*)?   # optional timestamp
    \[?{PREFIX_ALT}({KEY})\]?                       # speaker label (brackets optional)
    :\s*(.+)$
    """,
    re.M | re.VERBOSE,
)


def bracketed_forms(key: str) -> list[str]:
    """Every bracketed spelling for a given key, e.g. for key='A':
       ['[Speaker A]', '[说话人A]', '[与会者A]', '[发言人A]']."""
    return [f"[{prefix}{sep}{key}]" for prefix, sep in PREFIXES]


def bare_forms_regex(key: str) -> re.Pattern:
    """Match a bare (unbracketed) reference like `Speaker 1` or `说话人A`,
    but NOT when it's already inside brackets, and not when followed by
    another alphanumeric character (avoids matching `Speaker A` inside
    `Speaker AB` when key='A')."""
    key_re = re.escape(key)
    return re.compile(rf"(?<!\[){PREFIX_ALT}{key_re}(?![A-Z\d])")


def scan_speakers(content: str) -> "OrderedDict[str, dict]":
    """Find every speaker label with samples + counts. Preserves
    first-appearance order so prompts read out as 1 → 2 → 3 (or A → B → C)."""
    speakers: "OrderedDict[str, dict]" = OrderedDict()

    # Pass 1: transcript-style lines (collect samples + timestamp range).
    for m in TRANSCRIPT_LINE.finditer(content):
        ts, key, text = m.groups()
        info = speakers.setdefault(
            key,
            {"transcript_lines": 0, "samples": [], "first_ts": None, "last_ts": None, "summary_refs": 0},
        )
        info["transcript_lines"] += 1
        if ts:
            if info["first_ts"] is None:
                info["first_ts"] = ts
            info["last_ts"] = ts
        if len(info["samples"]) < 3 and len(text.strip()) > 4:
            info["samples"].append((ts, text.strip()[:120]))

    # Pass 2: count references elsewhere in the document.
    bracket_pat = re.compile(rf"\[{PREFIX_ALT}({KEY})\]")
    plain_pat = re.compile(rf"(?<!\[){PREFIX_ALT}({KEY})(?![A-Z\d])")
    all_brackets = bracket_pat.findall(content)
    all_plain = plain_pat.findall(content)
    for key in set(all_brackets) | set(all_plain):
        info = speakers.setdefault(
            key,
            {"transcript_lines": 0, "samples": [], "first_ts": None, "last_ts": None, "summary_refs": 0},
        )
        bracket_total = all_brackets.count(key)
        info["summary_refs"] = max(0, bracket_total - info["transcript_lines"]) + all_plain.count(key)

    return speakers


def parse_map_arg(s: str) -> dict:
    """Parse '--map 1=Alice,2=Bob' or '--map A=Alice,B=Bob' into a dict."""
    out = {}
    for piece in s.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "=" not in piece:
            sys.exit(f"Invalid --map entry: {piece!r}, expected like 1=Alice,2=Bob or A=Alice,B=Bob")
        k, v = piece.split("=", 1)
        # Letter keys are normalized to uppercase; digit keys stay numeric.
        k = k.strip()
        out[k.upper() if k.isalpha() else k] = v.strip()
    return out


def apply_replacements(content: str, mapping: dict) -> tuple[str, dict]:
    """Apply name substitutions. Returns (new_content, per-key counts).

    For each key→name, this:
      1. Replaces every bracketed form (`[Speaker A]`, `[说话人A]`, …) with `[name]`
      2. Replaces bare references (`Speaker A foo`, `说话人A foo`) with the bare name
    """
    counts = {}
    for key, name in mapping.items():
        total = 0

        # 1) Bracketed forms.
        for bracketed in bracketed_forms(key):
            c = content.count(bracketed)
            content = content.replace(bracketed, f"[{name}]")
            total += c

        # 2) Bare references in prose.
        pat = bare_forms_regex(key)
        matches = pat.findall(content)
        content = pat.sub(name, content)
        total += len(matches)

        counts[key] = total
    return content, counts


def main():
    parser = argparse.ArgumentParser(
        description="Substitute Speaker placeholders in a meeting note with real names."
    )
    parser.add_argument("note", help="Generated meeting note (.md) to edit in place")
    parser.add_argument(
        "--map",
        help="Skip interactive prompts; e.g. --map 1=Alice,2=Bob or --map A=Alice,B=Bob. "
             "Keys absent from the file are silently dropped.",
    )
    parser.add_argument("--no-backup", action="store_true", help="Skip writing a .bak before edit")
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip the 'continue?' prompt (typical with --map for scripting)",
    )
    args = parser.parse_args()

    note = Path(args.note).expanduser().resolve()
    if not note.exists():
        sys.exit(f"File not found: {note}")

    content = note.read_text(encoding="utf-8")
    speakers = scan_speakers(content)
    if not speakers:
        sys.exit(
            "No Speaker / [Speaker X] / [说话人X] labels found. The note may already "
            "use real names, or the transcribe step didn't produce speaker labels."
        )

    print(f"\nFound {len(speakers)} distinct speaker(s) in {note.name}\n")
    for key, info in speakers.items():
        ts_range = ""
        if info["first_ts"] and info["last_ts"]:
            ts_range = f"  ({info['first_ts']} – {info['last_ts']})"
        print(
            f"── Speaker {key}: {info['transcript_lines']} transcript line(s){ts_range}, "
            f"{info['summary_refs']} reference(s) elsewhere"
        )
        for ts, text in info["samples"]:
            ts_str = f"[{ts}] " if ts else ""
            print(f"   {ts_str}{text}")
        if not info["samples"]:
            print("   (no transcript samples — only referenced in summary sections)")
        print()

    # Get mapping (interactive or via --map)
    if args.map:
        mapping = parse_map_arg(args.map)
        mapping = {k: v for k, v in mapping.items() if k in speakers}
    else:
        mapping = {}
        print("=" * 60)
        print("Enter a real name for each speaker. Press Enter to keep label as-is.")
        print("=" * 60)
        for key in speakers.keys():
            try:
                ans = input(f"Speaker {key} → ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return
            if ans:
                mapping[key] = ans

    if not mapping:
        print("No substitutions provided. Exiting without changes.")
        return

    print("\nWill substitute:")
    for key, name in mapping.items():
        print(f"  Speaker {key} → {name}")
    if not args.no_confirm:
        try:
            ans = input("\nProceed? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if ans not in ("", "y", "yes"):
            print("Aborted.")
            return

    if not args.no_backup:
        bak = note.with_suffix(note.suffix + ".bak")
        shutil.copy2(note, bak)
        print(f"Backup: {bak}")

    new_content, counts = apply_replacements(content, mapping)
    note.write_text(new_content, encoding="utf-8")

    total = sum(counts.values())
    print(f"\n✅ Done. {total} substitution(s) made:")
    for key, n in counts.items():
        print(f"   Speaker {key} → {mapping[key]}: {n}")
    print(f"   Wrote: {note}")


if __name__ == "__main__":
    main()
