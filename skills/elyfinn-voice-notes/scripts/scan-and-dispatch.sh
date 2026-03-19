#!/bin/bash
#
# scan-and-dispatch.sh
# - Scan notes/transcripts and dispatch tagged TODOs into registries:
#   @Codex/@Claude  -> tasks/code-tasks.json (as "todo" entries)
#   @文章           -> tasks/content-tasks.json (as "todo" entries)
#   @提醒 + cron    -> config/cron/proactive-reminders.crontab (generated section)
#
# This script is designed to be run by cron/launchd.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

STATE_FILE="$REPO_ROOT/.clawdbot/proactive-work-state.json"
REMINDERS_FILE="$REPO_ROOT/.clawdbot/proactive-reminders.json"

CODE_TASKS_FILE="$REPO_ROOT/tasks/code-tasks.json"
CONTENT_TASKS_FILE="$REPO_ROOT/tasks/content-tasks.json"
CRON_FILE="$REPO_ROOT/config/cron/proactive-reminders.crontab"

DEFAULT_OBSIDIAN_VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian"
DEFAULT_OBSIDIAN_MEETINGS="$DEFAULT_OBSIDIAN_VAULT/meetings"

usage() {
  cat <<'EOF'
Usage:
  ./skills/proactive-work/scripts/scan-and-dispatch.sh [--since-hours N] [--all] [--root PATH ...]
  ./skills/proactive-work/scripts/scan-and-dispatch.sh --fire-reminder <reminder-id>

Options:
  --since-hours N   Scan files modified within last N hours (default: 48)
  --all             Scan all files (ignore mtime cutoff)
  --root PATH       Extra root folder/file to scan (repeatable)

Env:
  PROACTIVE_OBSIDIAN_MEETINGS  Override Obsidian meetings folder path
  PROACTIVE_SCAN_OBSIDIAN=0    Disable Obsidian scan even if folder exists
EOF
}

SINCE_HOURS="48"
SCAN_ALL="0"
EXTRA_ROOTS=()
FIRE_REMINDER_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --since-hours)
      SINCE_HOURS="${2:-}"
      shift 2
      ;;
    --all)
      SCAN_ALL="1"
      shift
      ;;
    --root)
      EXTRA_ROOTS+=("${2:-}")
      shift 2
      ;;
    --fire-reminder)
      FIRE_REMINDER_ID="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -n "$FIRE_REMINDER_ID" ]; then
  python3 - "$REMINDERS_FILE" "$FIRE_REMINDER_ID" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

reminders_path = Path(sys.argv[1])
rid = sys.argv[2]

now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
log_path = Path.home() / ".clawdbot" / "reminders.log"
log_path.parent.mkdir(parents=True, exist_ok=True)

data = {"reminders": []}
if reminders_path.exists():
    data = json.loads(reminders_path.read_text(encoding="utf-8"))

reminder = next((r for r in data.get("reminders", []) if r.get("id") == rid), None)
if not reminder:
    log_path.write_text(f"[{now}] reminder_not_found id={rid}\n", encoding="utf-8", errors="replace")
    sys.exit(0)

message = reminder.get("message", "")
source = reminder.get("source", {})
src = f"{source.get('path','')}:{source.get('line','')}".strip(":")

with log_path.open("a", encoding="utf-8", errors="replace") as f:
    f.write(f"[{now}] REMINDER {rid} {message} (source: {src})\n")

reminder["lastFiredAt"] = now
reminder["fireCount"] = int(reminder.get("fireCount") or 0) + 1
reminder["status"] = reminder.get("status") or "active"
reminders_path.parent.mkdir(parents=True, exist_ok=True)
reminders_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  exit 0
fi

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$CRON_FILE")"

ROOTS=()
ROOTS+=("$REPO_ROOT/memory")

if [ "${PROACTIVE_SCAN_OBSIDIAN:-1}" != "0" ]; then
  OBSIDIAN_MEETINGS="${PROACTIVE_OBSIDIAN_MEETINGS:-$DEFAULT_OBSIDIAN_MEETINGS}"
  if [ -d "$OBSIDIAN_MEETINGS" ]; then
    ROOTS+=("$OBSIDIAN_MEETINGS")
  fi
fi

for r in "${EXTRA_ROOTS[@]:-}"; do
  [ -n "$r" ] && ROOTS+=("$r")
done

EXTRACTOR="$SCRIPT_DIR/extract-todos.py"
if [ ! -f "$EXTRACTOR" ]; then
  echo "Extractor not found: $EXTRACTOR" >&2
  exit 1
fi

tmp_json="$(mktemp)"
trap 'rm -f "$tmp_json"' EXIT

extract_args=( "--roots" )
for r in "${ROOTS[@]}"; do
  extract_args+=( "$r" )
done

if [ "$SCAN_ALL" = "1" ]; then
  extract_args+=( "--all" )
else
  extract_args+=( "--since-hours" "$SINCE_HOURS" )
fi

python3 "$EXTRACTOR" "${extract_args[@]}" > "$tmp_json"

python3 - "$tmp_json" "$STATE_FILE" "$CODE_TASKS_FILE" "$CONTENT_TASKS_FILE" "$REMINDERS_FILE" "$CRON_FILE" "$REPO_ROOT" <<'PY'
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

extracted_path = Path(sys.argv[1])
state_path = Path(sys.argv[2])
code_tasks_path = Path(sys.argv[3])
content_tasks_path = Path(sys.argv[4])
reminders_path = Path(sys.argv[5])
cron_path = Path(sys.argv[6])
repo_root = sys.argv[7]

now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]

def ensure_registry(path: Path, description: str):
    if path.exists():
        return
    save_json(path, {"description": description, "tasks": []})

def unique_id(existing_ids: set[str], base: str) -> str:
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}-{i}" in existing_ids:
        i += 1
    return f"{base}-{i}"

extracted = load_json(extracted_path, {"items": []})
items = extracted.get("items", [])

state = load_json(state_path, {"seen": {}, "lastRunAt": None})
seen = state.get("seen", {})

ensure_registry(code_tasks_path, "代码开发任务（Codex/Claude Code）")
ensure_registry(content_tasks_path, "内容创作任务（小说、文章、翻译）")

code_reg = load_json(code_tasks_path, {"tasks": []})
content_reg = load_json(content_tasks_path, {"tasks": []})
existing_code_ids = {t.get("id") for t in code_reg.get("tasks", []) if t.get("id")}
existing_content_ids = {t.get("id") for t in content_reg.get("tasks", []) if t.get("id")}

reminders = load_json(reminders_path, {"reminders": []})
existing_reminder_ids = {r.get("id") for r in reminders.get("reminders", []) if r.get("id")}

created_code = 0
created_content = 0
created_reminders = 0
generated_cron = []

def should_dispatch(item) -> bool:
    fp = item.get("fingerprint")
    return bool(fp) and fp not in seen

for item in items:
    if not should_dispatch(item):
        continue

    fp = item["fingerprint"]
    route = item.get("route") or "misc"
    text = (item.get("text") or "").strip()
    tags = item.get("tags") or []

    # Always record state (even if we decide not to dispatch)
    state_entry = {
        "firstSeenAt": now,
        "route": route,
        "text": text,
        "source": {"path": item.get("sourcePath"), "line": item.get("sourceLine")},
    }

    if route == "code":
        agent = "claude" if "Claude" in tags else "codex"
        base = f"pw-code-{short_hash(fp)}"
        task_id = unique_id(existing_code_ids, base)
        existing_code_ids.add(task_id)
        code_reg["tasks"].append(
            {
                "id": task_id,
                "description": text,
                "agent": agent,
                "status": "todo",
                "createdAt": now,
                "source": {
                    "path": item.get("sourcePath"),
                    "line": item.get("sourceLine"),
                    "raw": item.get("rawLine"),
                    "tags": tags,
                },
            }
        )
        created_code += 1
        state_entry["dispatchedAt"] = now
        state_entry["taskId"] = task_id
    elif route == "content":
        base = f"pw-content-{short_hash(fp)}"
        task_id = unique_id(existing_content_ids, base)
        existing_content_ids.add(task_id)
        content_reg["tasks"].append(
            {
                "id": task_id,
                "title": text,
                "type": "article",
                "status": "todo",
                "createdAt": now,
                "source": {
                    "path": item.get("sourcePath"),
                    "line": item.get("sourceLine"),
                    "raw": item.get("rawLine"),
                    "tags": tags,
                },
            }
        )
        created_content += 1
        state_entry["dispatchedAt"] = now
        state_entry["taskId"] = task_id
    elif route == "reminder":
        cron_expr = item.get("cron")
        base = f"pw-reminder-{short_hash(fp)}"
        rid = unique_id(existing_reminder_ids, base)
        existing_reminder_ids.add(rid)
        reminders["reminders"].append(
            {
                "id": rid,
                "message": text,
                "cron": cron_expr,
                "status": "active" if cron_expr else "needs_schedule",
                "createdAt": now,
                "source": {"path": item.get("sourcePath"), "line": item.get("sourceLine")},
            }
        )
        created_reminders += 1
        state_entry["dispatchedAt"] = now
        state_entry["reminderId"] = rid

        if cron_expr:
            cmd = f"{cron_expr} /bin/zsh -lc '{repo_root}/skills/proactive-work/scripts/scan-and-dispatch.sh --fire-reminder {rid}'"
            generated_cron.append((rid, cmd, item.get("sourcePath"), item.get("sourceLine")))
    else:
        # Un-tagged tasks are tracked in state but not dispatched.
        pass

    seen[fp] = state_entry

save_json(code_tasks_path, code_reg)
save_json(content_tasks_path, content_reg)
save_json(reminders_path, reminders)

state["seen"] = seen
state["lastRunAt"] = now
save_json(state_path, state)

# Generate cron file section for reminders (do not touch other lines).
BEGIN = "# BEGIN proactive-work reminders (generated)\n"
END = "# END proactive-work reminders (generated)\n"

file_header = [
    "# proactive-reminders.crontab",
    "# - Install: crontab config/cron/proactive-reminders.crontab",
    "# - Generated entries call scan-and-dispatch.sh --fire-reminder <id>",
    "",
]

generated_lines: list[str] = []
for rid, cmd, src_path, src_line in sorted(generated_cron, key=lambda x: x[0]):
    src = f"{src_path}:{src_line}"
    generated_lines.append(f"# id={rid} source={src}")
    generated_lines.append(cmd)
    generated_lines.append("")

content = cron_path.read_text(encoding="utf-8") if cron_path.exists() else ""
if BEGIN in content and END in content:
    pre, rest = content.split(BEGIN, 1)
    _, post = rest.split(END, 1)
    new_content = pre + BEGIN + "\n".join(generated_lines).rstrip() + "\n" + END + post.lstrip("\n")
else:
    new_content = "\n".join(file_header) + "\n" + BEGIN + "\n".join(generated_lines).rstrip() + "\n" + END

cron_path.parent.mkdir(parents=True, exist_ok=True)
cron_path.write_text(new_content.strip("\n") + "\n", encoding="utf-8")

print(
    json.dumps(
        {
            "created": {"code": created_code, "content": created_content, "reminders": created_reminders},
            "cronEntries": len(generated_cron),
        },
        ensure_ascii=False,
    )
)
PY
