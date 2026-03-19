#!/usr/bin/env python3
"""
Extract TODO/action items from notes and transcripts.

Targets:
  - Markdown checkboxes: - [ ] ...
  - Inline TODO markers: TODO: ...
  - @tags: @Codex / @文章 / @提醒 / ...

Output: JSON to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional


CHECKBOX_TODO_RE = re.compile(r"^\s*[-*]\s+\[\s\]\s+(?P<text>.+?)\s*$")
CHECKBOX_DONE_RE = re.compile(r"^\s*[-*]\s+\[\s*[xX]\s*\]\s+")
HEADING_TAG_RE = re.compile(r"^\s{0,3}#{1,6}\s+@(?P<tag>\S+)\s*$")
ACTION_HEADING_RE = re.compile(r"^\s{0,3}###\s+@(?P<tag>\S+)\s*$")
INLINE_TODO_RE = re.compile(r"^\s*(?:-|\*|\d+\.)?\s*TODO\s*[:：]\s*(?P<text>.+?)\s*$", re.IGNORECASE)
TAG_TOKEN_RE = re.compile(r"@(?P<tag>[A-Za-z0-9_\-\u4e00-\u9fff]+)")

KNOWN_TAGS = {
    "Codex": "code",
    "Claude": "code",
    "文章": "content",
    "提醒": "reminder",
    "调研": "research",
    "设计": "design",
    "北哥": "human",
    "凡哥": "orchestrator",
}


CRON_HINT_RE = re.compile(
    r"(?:^|\s)cron\s*[:=]\s*(?P<expr>(?:[@\w*/,\-]+\s+){4}[@\w*/,\-]+)(?:\s+|$)",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_files(roots: list[Path], since_hours: Optional[int], include_hidden: bool) -> Iterable[Path]:
    cutoff = None
    if since_hours is not None:
        cutoff = datetime.now() - timedelta(hours=since_hours)

    exts = {".md", ".markdown", ".mdx", ".txt"}
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            paths = [root]
        else:
            paths = root.rglob("*")
        for p in paths:
            if p.is_dir():
                continue
            if not include_hidden:
                parts = p.relative_to(root).parts if root.is_dir() else p.parts
                if any(part.startswith(".") for part in parts):
                    continue
            if p.suffix.lower() not in exts:
                continue
            try:
                if cutoff is not None:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime)
                    if mtime < cutoff:
                        continue
            except OSError:
                continue
            yield p


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_known_tags(text: str) -> str:
    # remove tag tokens like "@Codex" "@文章"
    for tag in KNOWN_TAGS.keys():
        text = re.sub(rf"(?<!\w)@{re.escape(tag)}(?!\w)", "", text)
    return _normalize_space(text)


def _extract_tags(text: str) -> list[str]:
    tags = []
    for m in TAG_TOKEN_RE.finditer(text):
        t = m.group("tag")
        if t in KNOWN_TAGS and t not in tags:
            tags.append(t)
    return tags


def _route_for(tags: list[str], section_tag: Optional[str]) -> str:
    for t in tags:
        route = KNOWN_TAGS.get(t)
        if route in {"code", "content", "reminder"}:
            return route
    if section_tag and section_tag in KNOWN_TAGS:
        route = KNOWN_TAGS[section_tag]
        if route in {"code", "content", "reminder"}:
            return route
    return "misc"


def _parse_cron(text: str) -> Optional[str]:
    m = CRON_HINT_RE.search(text)
    if m:
        return _normalize_space(m.group("expr"))

    # fallback: if the beginning looks like 5 cron fields, treat it as cron expr.
    tokens = _normalize_space(text).split(" ")
    if len(tokens) >= 5 and all(re.fullmatch(r"[@\w*/,\-]+", tok) for tok in tokens[:5]):
        return " ".join(tokens[:5])
    return None


def _fingerprint(source_path: str, text: str, route: str) -> str:
    h = hashlib.sha1()
    h.update(source_path.encode("utf-8"))
    h.update(b"\n")
    h.update(text.encode("utf-8"))
    h.update(b"\n")
    h.update(route.encode("utf-8"))
    return h.hexdigest()


@dataclass(frozen=True)
class ExtractedItem:
    fingerprint: str
    route: str
    text: str
    tags: list[str]
    cron: Optional[str]
    sourcePath: str
    sourceLine: int
    rawLine: str


def extract_from_text(text: str, source_path: str) -> list[ExtractedItem]:
    items: list[ExtractedItem] = []
    section_tag: Optional[str] = None
    explicit_tag_line_re = re.compile(r"^@(?P<tag>[A-Za-z0-9_\\-\\u4e00-\\u9fff]+)\\s+(?P<rest>.+)$")

    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if CHECKBOX_DONE_RE.match(line):
            continue

        m_heading = HEADING_TAG_RE.match(line) or ACTION_HEADING_RE.match(line)
        if m_heading:
            section_tag = m_heading.group("tag")
            continue

        if line.strip().startswith("#"):
            section_tag = None
            continue

        task_text: Optional[str] = None
        if (m := CHECKBOX_TODO_RE.match(line)) is not None:
            task_text = m.group("text")
        elif (m := INLINE_TODO_RE.match(line)) is not None:
            task_text = m.group("text")

        if not task_text:
            s = line.strip()
            # Support explicit one-tag lines like "@提醒 cron: ...", but avoid multi-tag mappings like "@Codex/@Claude ..."
            if s.startswith("@") and "/" not in s.split(" ", 1)[0]:
                m = explicit_tag_line_re.match(s)
                if m and m.group("tag") in KNOWN_TAGS:
                    task_text = s
                else:
                    continue
            else:
                continue

        tags = _extract_tags(task_text)
        route = _route_for(tags, section_tag)
        clean = _strip_known_tags(task_text)
        if not clean:
            continue

        cron = _parse_cron(task_text) if route == "reminder" else None
        fp = _fingerprint(source_path, clean, route)
        items.append(
            ExtractedItem(
                fingerprint=fp,
                route=route,
                text=clean,
                tags=tags if tags else ([section_tag] if section_tag else []),
                cron=cron,
                sourcePath=source_path,
                sourceLine=idx,
                rawLine=line.rstrip("\n"),
            )
        )

    return items


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract TODOs/@tags from notes")
    parser.add_argument(
        "--roots",
        nargs="+",
        default=[],
        help="Root folders/files to scan (repeatable via space-separated list)",
    )
    parser.add_argument("--since-hours", type=int, default=48, help="Only scan files modified in last N hours")
    parser.add_argument("--all", action="store_true", help="Scan all files (ignore mtime cutoff)")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden files/folders")
    args = parser.parse_args(argv)

    roots = [Path(os.path.expanduser(r)).resolve() for r in args.roots if r.strip()]
    since_hours = None if args.all else args.since_hours

    extracted: list[ExtractedItem] = []
    for path in _iter_files(roots, since_hours=since_hours, include_hidden=args.include_hidden):
        try:
            content = _read_text(path)
        except Exception:
            continue
        extracted.extend(extract_from_text(content, str(path)))

    # Stable sort: route then source path/line
    extracted.sort(key=lambda x: (x.route, x.sourcePath, x.sourceLine))

    out = {
        "generatedAt": _now_iso(),
        "roots": [str(r) for r in roots],
        "items": [asdict(i) for i in extracted],
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
