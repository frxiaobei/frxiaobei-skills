---
name: elyfinn-voice-notes
description: |
  Smart voice memo processor with automatic recording type classification.
  Classifies recordings into 7 types and generates type-specific formatted notes.
  
  **MUST use this skill when user mentions:**
  - Process/scan voice memos, Voice Memos, recordings
  - Convert recordings to notes (meetings, lectures, interviews, etc.)
  - Process keynote/lecture/podcast recordings → extracts key insights + quotes
  - Process interview recordings → generates evaluation report with scoring
  - Process customer/sales call recordings → tracks commitments and follow-ups
  - "帮我处理录音"、"语音备忘录"、"录音转笔记"
  
  **Supported recording types (auto-detected):**
  - meeting: Internal meetings → TODO list with assignees
  - keynote: Lectures/conferences/podcasts → Key insights + quotes
  - interview: Job interviews → Evaluation report with 5-dimension scoring
  - customer: Sales/BD calls → Commitment tracking
  - brainstorm: Brainstorming sessions → Ideas with feasibility analysis
  - consult: Expert consultations → Insights summary
  - note: Personal voice notes → Clean text formatting
  
  **Do NOT use when:**
  - User wants to record audio (use system Voice Memos app)
  - Only need raw transcription without formatting (use gemini-transcribe)
  - Scan meeting notes or extract TODOs from text files (not voice memos)
---

# Elyfinn Voice Notes

Smart voice memo processor that automatically classifies recordings and generates type-specific formatted notes.

## Preferences (config.yaml)

Check config file existence (priority order):

```bash
test -f ".openclaw/skills/elyfinn-voice-notes/config.yaml" && echo "project"
test -f "$HOME/.openclaw/skills/elyfinn-voice-notes/config.yaml" && echo "user"
```

| Result | Action |
|--------|--------|
| Found | Read and apply settings |
| Not found | **MUST** run first-time setup (see below) |

**config.yaml Supports**: Output language | Uncertain handling | Save location | Auto-scan settings

Schema: [references/config/config-schema.md](references/config/config-schema.md)

### First-Time Setup (BLOCKING)

**CRITICAL**: When config.yaml is not found, you **MUST** run the first-time setup before ANY recording processing. This is a **BLOCKING** operation — do NOT proceed to scan or process recordings until setup is complete.

Full reference: [references/config/first-time-setup.md](references/config/first-time-setup.md)

Use `AskUserQuestion` to present all questions in ONE message. **WAIT for user response** before proceeding — do NOT continue until the user has answered.

After user answers, create config.yaml at the chosen location, confirm "✅ Preferences saved to [path]", then continue with processing.

**Questions to ask:**

```
🎙️ **Voice Notes Setup**

Let me configure your preferences for processing voice recordings.

**1. Recording Source**
Where are your voice recordings stored?
- 📱 iPhone Voice Memos (Recommended)
  macOS: ~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings
- 📂 Custom folder (please specify the full path)

**2. Output Location**
Where should I save the generated notes?
- 📄 ~/Documents/voice-notes (Recommended)
- 📔 Obsidian vault (please specify your vault path, e.g. ~/Documents/Obsidian/meetings)
- 📂 Custom folder (please specify)

**3. Output Language**
What language should the notes be in?
- 🌐 Auto (Recommended) - Follows recording language
- 🇨🇳 Always Chinese
- 🇺🇸 Always English

**4. When AI is Uncertain**
If I'm not sure about the recording type, what should I do?
- ❓ Ask you (Recommended) - Confirm before processing
- 🤖 Auto-process - Trust my best guess

**5. Auto-Scan**
Should I automatically check for new recordings?
- ⏰ Every 30 minutes (Recommended)
- ⏰ Every hour
- ❌ Manual only
```

**After setup**: Create `~/.openclaw/skills/elyfinn-voice-notes/config.yaml` with user's choices, then proceed.

## Quick Start

```bash
# Scan and dispatch from last 48 hours (recommended)
./skills/elyfinn-voice-notes/scripts/scan-and-dispatch.sh --since-hours 48

# Full scan (caution: may create many todo entries)
./skills/elyfinn-voice-notes/scripts/scan-and-dispatch.sh --all
```

Output & Side Effects:
- `@Codex/@Claude` → writes to `tasks/code-tasks.json` (status: "todo")
- `@article` → writes to `tasks/content-tasks.json` (status: "todo")
- `@reminder` (with cron expression) → writes to `config/cron/proactive-reminders.crontab`
- Dedup state → `.clawdbot/elyfinn-voice-notes-state.json`
- Reminder registry → `.clawdbot/proactive-reminders.json`

## Data Sources

| Source | Scan Method | Status |
|--------|-------------|--------|
| **Meeting notes** | Obsidian `meetings/` directory | ✅ Implemented |
| **Voice memos** | macOS Voice Memos → Gemini transcription | ✅ Implemented |
| **Git log** | Auto-generate changelog | 🔜 Planned |
| **GitHub Issues** | `gh issue list` | 🔜 Planned |
| **Code TODOs** | `grep -r "TODO:" src/` | 🔜 Planned |
| **Project BACKLOG** | TASKS.md in each project | 🔜 Planned |

### Obsidian Configuration

`scan-and-dispatch.sh` scans by default:
- `workspace/memory/`
- `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/meetings/` (if exists)

Override with environment variables:
- `PROACTIVE_OBSIDIAN_MEETINGS=/path/to/meetings`
- `PROACTIVE_SCAN_OBSIDIAN=0` (disable Obsidian scan)

---

## Recording Type Classification

The skill automatically classifies voice recordings into 7 types:

| Type | Characteristics | Output Format |
|------|-----------------|---------------|
| `meeting` | Multiple participants, discussions, task assignments | TODO list with @assignees |
| `keynote` | Single speaker, structured content, insights/quotes | Key points + quotes |
| `interview` | Q&A format, interviewer + candidate | 5-dimension evaluation report |
| `customer` | Business context, requirements, pricing | Commitment tracking |
| `brainstorm` | Divergent thinking, multiple ideas | Ideas with feasibility |
| `consult` | Expert advice, asking for guidance | Insights summary |
| `note` | Personal voice memo, self-talk | Clean formatted text |

### Classification Logic

1. **Participant count**: Single → note/keynote, Multiple → meeting/brainstorm/customer
2. **Dialog pattern**: One-way → keynote, Q&A → interview, Discussion → meeting
3. **Content type**: Insights/arguments → keynote, Task assignments → meeting, Business negotiation → customer
4. **Context clues**: "interview"/"candidate" → interview, "customer"/"pricing" → customer

---

## Task Dispatch

### ⚠️ Important: Confirmation Mechanism

**TODOs extracted from voice memos must be discussed with user first before batch dispatch!**

Flow:
```
Transcription complete → Extract all action items → Send to user for review
                                                           ↓
                                                   Discuss & align understanding
                                                           ↓
                                                      Batch dispatch
```

**Purpose**: Prevent AI misunderstanding voice content; ensure alignment before action.

---

Tasks are dispatched based on @tags:

| Tag | Task Type | Execution | Skill/Tool |
|-----|-----------|-----------|------------|
| `@user` | Human task | Push notification | Telegram |
| `@assistant` | Orchestrator task | Direct execution | Built-in tools |
| `@Codex` | Write code | Spawn agent | `agent-swarm` |
| `@Claude` | Write code (frontend) | Spawn agent | `agent-swarm` |
| `@reminder` | Set reminder | Create cron/calendar | `cron` / `gcal` |
| `@article` | Write article | Draft + publish | `baoyu-post-to-*` |
| `@research` | Information search | Search & summarize | `web_search` |
| `@design` | Design/images | Generate image | `baoyu-image-gen` |

---

## Tag Format (Recommended)

### Meeting Template (grouped by assignee)

```markdown
### @Codex
- [ ] Implement elyfinn-voice-notes scan and dispatch

### @article
- [ ] Write "Agent Swarm Task Discovery" blog post

### @reminder
- [ ] cron: 0 10 * * * Remind to configure Voice Memos disk access
```

### @reminder cron syntax

Only `@reminder` with cron expression will auto-generate to `config/cron/proactive-reminders.crontab`:
- Recommended: `cron: 0 10 * * * your reminder content`
- Also supported: 5-field cron at the beginning (e.g., `0 10 * * * your reminder content`)

---

## Voice Memos Processing

### Prerequisites

macOS System Settings → Privacy & Security → Full Disk Access → Terminal ✅

### Processing Flow

```
Voice file (.m4a/.qta)
    ↓
Classify recording type (Gemini)
    ↓
Select type-specific template
    ↓
Generate formatted notes (Gemini)
    ↓
Save to Obsidian meetings/
    ↓
Dispatch tasks by @tags
```

### Scripts

```bash
# Scan and process new voice memos
python3 scripts/scan-voice-memos.py

# View statistics
python3 scripts/db.py --stats

# View pending
python3 scripts/db.py --pending
```

### Data Storage

- Database: `data/elyfinn-voice-notes/proactive.db` (SQLite)
- State flow: `pending → processing → processed/failed`
- Auto-retry on failure (max 3 times)

### Output Templates

Templates for each recording type are in `templates/`:
- `meeting.md` - Internal meetings (TODO list)
- `keynote.md` - Lectures/conferences (insights + quotes)
- `interview.md` - Job interviews (5-dimension evaluation)
- `customer.md` - Sales/BD calls (commitment tracking)
- `brainstorm.md` - Brainstorming (ideas + feasibility)
- `consult.md` - Expert consultations (insights summary)
- `note.md` - Personal notes (clean text)

---

## Meeting Notes Scanning

### Directory Structure

```
Obsidian/
└── meetings/
    ├── 2026-02-28-Customer-A.md
    └── templates/
        └── meeting.md
```

### Scan Script

```bash
python3 scripts/scan-meetings.py           # Scan last 24h
python3 scripts/scan-meetings.py --hours 48  # Scan last 48h
python3 scripts/scan-meetings.py --all       # Scan all incomplete
python3 scripts/scan-meetings.py --json      # Output JSON
```

---

## Cron Jobs

- Voice memos: Every 30 minutes (OpenClaw cron)
- Meeting notes: Daily at 9:00 AM

---

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `agent-swarm` | Receives `@Codex` `@Claude` tasks, spawns agents |
| `baoyu-post-to-*` | Receives `@article` tasks, writes & publishes |
| `gcal` | Receives `@reminder` tasks, creates calendar events |
| `gemini-transcribe` | Used for raw transcription |

**This skill discovers tasks; other skills execute them.**

---

## Directory Structure

```
skills/elyfinn-voice-notes/
├── SKILL.md                    # This file
├── scripts/
│   ├── scan-and-dispatch.sh    # Main entry point ⭐
│   ├── scan-voice-memos.py     # Voice memo processing ✅
│   ├── scan-meetings.py        # Meeting notes scan
│   ├── extract-todos.py        # Extract TODOs/@tags
│   ├── db.py                   # SQLite database
│   └── config.py               # User config loading
├── templates/                  # Type-specific prompt templates
│   ├── classification.md       # Recording type classification
│   ├── meeting.md
│   ├── keynote.md
│   ├── interview.md
│   ├── customer.md
│   ├── brainstorm.md
│   ├── consult.md
│   └── note.md
├── references/
│   └── config/
│       ├── config-schema.md    # Config file schema
│       └── first-time-setup.md # First-time setup flow
└── docs/
    └── recording-types-design.md
```

---

## Version History

### v0.3.0 (2026-03-19)
- Renamed from `proactive-work` to `elyfinn-voice-notes`
- Added first-time setup with `AskUserQuestion` flow
- Config file: `~/.openclaw/skills/elyfinn-voice-notes/config.yaml`
- Templates externalized to `templates/` directory
- English SKILL.md with auto-language output

### v0.2.0 (2026-03-19)
- Added automatic recording type classification (7 types)
- Type-specific output templates
- Keynote → insights + quotes (no TODOs)
- Interview → 5-dimension evaluation report
- Customer → commitment tracking

### v0.1.0 (2026-02-28)
- Initial version (as elyfinn-voice-notes)
- Meeting notes scanning
- Task dispatch logic design
