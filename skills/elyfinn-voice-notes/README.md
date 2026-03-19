# Elyfinn Voice Notes

Smart voice memo processor that automatically classifies recordings and generates type-specific formatted notes.

**No extra hardware. No subscription. Your data stays local.**

English | [中文](./README.zh.md)

## Features

- 🎙️ **Auto-classification**: Detects 7 recording types (meeting, keynote, interview, customer, brainstorm, consult, note)
- 📝 **Type-specific output**: Each type gets a tailored note format
- 🌐 **Language-adaptive**: Chinese recordings → Chinese notes, English → English
- 🔒 **Privacy-first**: All processing local, no data uploaded to cloud
- ⚙️ **Configurable**: First-time setup wizard, customizable paths

## Recording Types

| Type | Detected When | Output Format |
|------|---------------|---------------|
| `meeting` | Multiple participants, task discussions | TODO list with @assignees |
| `keynote` | Single speaker, insights/arguments | Key insights + quotes (no TODOs) |
| `interview` | Q&A format, interviewer + candidate | 5-dimension evaluation report |
| `customer` | Business context, pricing, requirements | Commitment tracking |
| `brainstorm` | Divergent thinking, idea generation | Ideas with feasibility analysis |
| `consult` | Expert advice, professional guidance | Insights summary |
| `note` | Personal voice memo, self-talk | Clean formatted text |

## Quick Start

### Prerequisites

- macOS (for Voice Memos integration)
- Python 3.10+
- [Gemini API access](https://ai.google.dev/) for transcription
- Full Disk Access for Terminal (System Settings → Privacy → Full Disk Access)

### Installation

```bash
# Clone to your OpenClaw skills directory
git clone https://github.com/elyfinn/elyfinn-voice-notes.git \
  ~/.openclaw/workspace/skills/elyfinn-voice-notes

# Install dependencies
pip install google-generativeai pyyaml
```

### First-Time Setup

When you first use the skill, it will ask you to configure:

1. **Recording Source** - iPhone Voice Memos (default) or custom folder
2. **Output Location** - Where to save generated notes
3. **Output Language** - Auto / Always Chinese / Always English
4. **Uncertain Handling** - Ask for confirmation or auto-process
5. **Auto-Scan** - Frequency of automatic scanning

Configuration is saved to `~/.openclaw/skills/elyfinn-voice-notes/config.yaml`

### Usage

```bash
# Scan and process new voice memos
python3 scripts/scan-voice-memos.py

# View statistics
python3 scripts/db.py --stats

# View pending recordings
python3 scripts/db.py --pending
```

## How It Works

```
Voice recording (.m4a)
    ↓
Transcribe (Gemini API)
    ↓
Classify type (AI analysis of first 3000 chars)
    ↓
Select template (templates/{type}.md)
    ↓
Generate formatted notes
    ↓
Save to configured output directory
```

## Configuration

Edit `~/.openclaw/skills/elyfinn-voice-notes/config.yaml`:

```yaml
# Where voice recordings are stored
recording_source: "~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"

# Where to save generated notes
output_directory: "~/Documents/voice-notes"

# Output language: auto | zh-CN | en
output_language: auto

# When uncertain about type: ask | auto
uncertain_handling: ask

# Auto-scan settings
auto_scan:
  enabled: true
  interval_minutes: 30
```

## Project Structure

```
elyfinn-voice-notes/
├── SKILL.md              # Skill documentation (for AI assistants)
├── README.md             # This file
├── scripts/
│   ├── scan-voice-memos.py   # Main processing script
│   ├── scan-meetings.py      # Meeting notes scanner
│   ├── db.py                 # SQLite database manager
│   └── config.py             # Configuration loader
├── templates/            # Type-specific prompt templates
│   ├── classification.md
│   ├── meeting.md
│   ├── keynote.md
│   ├── interview.md
│   ├── customer.md
│   ├── brainstorm.md
│   ├── consult.md
│   └── note.md
└── references/
    └── config/
        ├── config-schema.md
        └── first-time-setup.md
```

## Why Not Buy a Recording Device?

| Aspect | Dedicated Devices | This Solution |
|--------|-------------------|---------------|
| Hardware cost | $100-900 | $0 (use your phone) |
| Subscription | $0-240/year | $0 |
| Data ownership | Cloud/vendor | 100% local |
| Customization | Limited | Full (edit prompts) |
| Ecosystem lock-in | Yes (DingTalk/Feishu/etc.) | None |

## Requirements

- macOS 12+ (for Voice Memos access)
- Python 3.10+
- Gemini API key (set `GOOGLE_API_KEY` environment variable)

## License

MIT License - See [LICENSE](LICENSE) for details.

## Credits

Built by [Elyfinn](https://elyfinn.com) - Human + AI partnership.

Part of the [OpenClaw](https://github.com/openclaw/openclaw) skill ecosystem.
