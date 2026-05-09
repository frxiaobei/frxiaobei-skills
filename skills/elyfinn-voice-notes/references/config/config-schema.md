# config.yaml Schema

User preferences for elyfinn-voice-notes skill.

## Schema

```yaml
# Where voice recordings are stored
# Default: iPhone Voice Memos on macOS
recording_source: "~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"

# Where to save generated notes
# Default: ~/Documents/voice-notes
output_directory: "~/Documents/voice-notes"

# Output language for generated notes
# Options: "auto" | "zh-CN" | "en"
# Default: "auto" (follows transcript language)
output_language: auto

# What to do when AI is uncertain about recording type
# Options: "ask" | "auto"
# Default: "ask" (ask user to confirm)
uncertain_handling: ask

# Auto-scan settings
auto_scan:
  enabled: true
  interval_minutes: 30

# Custom type mappings (optional)
# Override default type prefix labels
type_labels:
  meeting: "Meeting"
  keynote: "Keynote"
  interview: "Interview"
  customer: "Customer"
  brainstorm: "Brainstorm"
  consult: "Consult"
  note: "Note"

# Optional: path to a markdown glossary of business/proper-noun terminology.
# When set, the contents are injected into the generation prompt so the LLM
# can correct ASR mistranscriptions (e.g., "克劳德口德" → "Claude Code",
# "阿贾" → "Agile"). Empty string disables.
# See references/glossary.md.example for format.
glossary_path: ""
```

## Field Details

### recording_source

Path to the directory containing voice recordings. Supports `~` for home directory.

Common values:
- iPhone Voice Memos (macOS): `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings`
- Custom folder: any path like `~/Dropbox/Recordings` or `/path/to/recordings`

### output_directory

Path where generated notes are saved. Supports `~` for home directory.

Examples:
- Default: `~/Documents/voice-notes`
- Obsidian: `~/Documents/Obsidian/meetings`
- iCloud: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/meetings`

### output_language

| Value | Behavior |
|-------|----------|
| `auto` | Output language follows transcript language (Chinese recording → Chinese notes) |
| `zh-CN` | Always output in Simplified Chinese |
| `en` | Always output in English |

### uncertain_handling

| Value | Behavior |
|-------|----------|
| `ask` | When classification confidence < 80%, ask user to confirm type before processing |
| `auto` | Always proceed with AI's best guess, even if uncertain |

### auto_scan

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Whether to auto-scan for new recordings |
| `interval_minutes` | number | How often to scan (15, 30, 60) |

### glossary_path

Path to a markdown file listing business/proper-noun terms that ASR commonly
mistranscribes. When set, the file's contents are injected into the LLM's
generation prompt so the model can restore canonical forms in the notes.

| Value | Behavior |
|-------|----------|
| `""` (empty, default) | Disabled. Prompt receives placeholder `(no glossary configured)` and skips the correction step. |
| `"~/path/to/glossary.md"` | Loads file contents and injects them under `[Business Terminology Glossary]` in the prompt. |

See [references/glossary.md.example](../glossary.md.example) for format. A
typical glossary lists entries like `Claude Code (often "克劳德口德",
"Cloud Code")` so the LLM knows what to correct.

**Recommended workflow**: copy `glossary.md.example` to a stable location
(e.g. `~/.config/elyfinn-voice-notes/glossary.md` or somewhere in your
dotfiles) and add your team's project names + people's names as you
encounter ASR errors.
