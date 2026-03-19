# First-Time Setup

## Overview

When no config.yaml is found, guide user through preference setup.

**BLOCKING OPERATION**: Setup MUST complete before processing recordings. Do NOT proceed until user has answered all questions.

## Config File Locations

Check in order (first found wins):

```bash
# Project-level
.openclaw/skills/elyfinn-voice-notes/config.yaml

# User-level (recommended)
$HOME/.openclaw/skills/elyfinn-voice-notes/config.yaml
```

## Setup Flow

```
No config.yaml found
        |
        v
+------------------------+
| AskUserQuestion        |
| (all questions in ONE) |
+------------------------+
        |
        v
   WAIT for user response
        |
        v
+------------------------+
| Create config.yaml     |
| Confirm saved          |
+------------------------+
        |
        v
    Continue processing
```

## Questions

Use `AskUserQuestion` to present ALL questions at once. **WAIT for user response** — this is an interactive flow.

### Question 1: Output Language

```
📝 **Output Language**

What language should the notes be in?

1. 🌐 Auto (Recommended) - Follows recording language
   Chinese recording → Chinese notes
   English recording → English notes

2. 🇨🇳 Always Chinese - All notes in Simplified Chinese

3. 🇺🇸 Always English - All notes in English
```

### Question 2: Uncertain Classification

```
🤔 **When AI is Uncertain**

If AI isn't sure about the recording type, what should I do?

1. ❓ Ask me (Recommended) - Confirm before processing
   "This sounds like a keynote (70% sure). Proceed?"

2. 🤖 Auto-process - Trust AI's best guess
```

### Question 3: Notes Location

```
📁 **Save Location**

Where should I save the notes?

1. 📔 Obsidian meetings/ (Recommended)
   ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/meetings/

2. 📂 Custom path...
   Enter your preferred directory
```

### Question 4: Auto-Scan

```
⏰ **Auto-Scan**

Should I automatically check for new recordings?

1. ✅ Yes, every 30 minutes (Recommended)
2. ✅ Yes, every hour
3. ❌ No, I'll run manually
```

## After Setup

1. Create directory: `mkdir -p $HOME/.openclaw/skills/elyfinn-voice-notes/`
2. Write config.yaml with selected values
3. Confirm: "✅ Preferences saved to ~/.openclaw/skills/elyfinn-voice-notes/config.yaml"
4. Mention: "You can edit this file anytime to change settings."
5. If auto-scan enabled, set up cron job
6. Continue with processing

## Default config.yaml Template

```yaml
# Elyfinn Voice Notes Preferences
# Edit this file to customize behavior

# Output language for generated notes
# Options: auto | zh-CN | en
output_language: auto

# What to do when AI is uncertain about recording type
# Options: ask | auto
uncertain_handling: ask

# Where to save generated notes
output_directory: "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/meetings"

# Auto-scan for new recordings
auto_scan:
  enabled: true
  interval_minutes: 30
```

## Re-running Setup

To reconfigure, user can:
1. Delete config.yaml and run again
2. Edit config.yaml directly
3. Say "重新设置语音笔记" or "voice notes setup"
