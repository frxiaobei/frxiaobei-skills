#!/usr/bin/env python3
"""
Configuration management for proactive-work skill.

Handles loading/saving EXTEND.md preferences.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

# Config file locations (priority order)
CONFIG_PATHS = [
    Path(".openclaw/skills/elyfinn-voice-notes/config.yaml"),  # Project-level
    Path.home() / ".openclaw/skills/elyfinn-voice-notes/config.yaml",  # User-level
]

# Default Voice Memos path (macOS)
DEFAULT_VOICE_MEMOS_PATH = str(Path.home() / "Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings")

# Default configuration
DEFAULT_CONFIG = {
    "recording_source": DEFAULT_VOICE_MEMOS_PATH,
    "output_directory": str(Path.home() / "Documents/voice-notes"),
    "output_language": "auto",
    "uncertain_handling": "ask",
    "auto_scan": {
        "enabled": True,
        "interval_minutes": 30
    },
    "type_labels": {
        "meeting": "Meeting",
        "keynote": "Keynote",
        "interview": "Interview",
        "customer": "Customer",
        "brainstorm": "Brainstorm",
        "consult": "Consult",
        "note": "Note"
    }
}


def find_config_file() -> Optional[Path]:
    """Find the first existing config file."""
    for path in CONFIG_PATHS:
        if path.exists():
            return path
    return None


def load_config() -> Dict[str, Any]:
    """Load configuration from EXTEND.md or return defaults."""
    config_path = find_config_file()
    
    if config_path is None:
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse YAML (skip markdown frontmatter if present)
        if content.startswith('---'):
            # Find end of frontmatter
            end = content.find('---', 3)
            if end != -1:
                content = content[end + 3:].strip()
        
        # Handle YAML content that might be in a code block
        if '```yaml' in content:
            start = content.find('```yaml') + 7
            end = content.find('```', start)
            content = content[start:end].strip()
        elif '```' in content:
            start = content.find('```') + 3
            end = content.find('```', start)
            content = content[start:end].strip()
        
        user_config = yaml.safe_load(content) or {}
        
        # Merge with defaults
        config = DEFAULT_CONFIG.copy()
        for key, value in user_config.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key].update(value)
            else:
                config[key] = value
        
        return config
        
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any], location: str = "user") -> Path:
    """Save configuration to EXTEND.md.
    
    Args:
        config: Configuration dictionary
        location: "user" or "project"
    
    Returns:
        Path where config was saved
    """
    if location == "project":
        config_path = Path(".openclaw/skills/elyfinn-voice-notes/config.yaml")
    else:
        config_path = Path.home() / ".openclaw/skills/elyfinn-voice-notes/config.yaml"
    
    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate YAML content
    yaml_content = yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Write with header comment
    content = f"""# Proactive Work Preferences
# Edit this file to customize behavior
# Delete this file to re-run setup

{yaml_content}
"""
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return config_path


def config_exists() -> bool:
    """Check if any config file exists."""
    return find_config_file() is not None


def get_output_directory(config: Dict[str, Any]) -> Path:
    """Get output directory from config, expanding ~ if present."""
    path_str = config.get("output_directory", DEFAULT_CONFIG["output_directory"])
    return Path(path_str).expanduser()


def get_recording_source(config: Dict[str, Any]) -> Path:
    """Get recording source directory from config, expanding ~ if present."""
    path_str = config.get("recording_source", DEFAULT_CONFIG["recording_source"])
    return Path(path_str).expanduser()


def should_ask_on_uncertain(config: Dict[str, Any]) -> bool:
    """Check if we should ask user when classification is uncertain."""
    return config.get("uncertain_handling", "ask") == "ask"


def get_output_language(config: Dict[str, Any]) -> str:
    """Get output language setting."""
    return config.get("output_language", "auto")


def get_type_label(config: Dict[str, Any], rec_type: str) -> str:
    """Get display label for a recording type."""
    labels = config.get("type_labels", DEFAULT_CONFIG["type_labels"])
    return labels.get(rec_type, rec_type.capitalize())


if __name__ == "__main__":
    # Test config loading
    import json
    
    print("=== Config Test ===")
    print(f"Config exists: {config_exists()}")
    print(f"Config path: {find_config_file()}")
    print(f"Config: {json.dumps(load_config(), indent=2)}")
