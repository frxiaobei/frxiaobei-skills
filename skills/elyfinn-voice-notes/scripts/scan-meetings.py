#!/usr/bin/env python3
"""
Meeting Notes Scanner

Scans the configured output directory for meeting notes and extracts action items.

Usage:
  python3 scan-meetings.py              # Scan last 24h
  python3 scan-meetings.py --hours 48   # Scan last 48h
  python3 scan-meetings.py --all        # Scan all incomplete
  
Data storage: SQLite (data/elyfinn-voice-notes/proactive.db)
"""

import os
import re
import json
import hashlib
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path for importing local modules
sys.path.insert(0, str(Path(__file__).parent))
from db import get_db
from config import load_config, get_output_directory

# Load config and get meetings directory
USER_CONFIG = load_config()
MEETINGS_DIR = get_output_directory(USER_CONFIG)
STATE_FILE = Path.home() / ".openclaw/workspace/.clawdbot/meeting-scan-state.json"  # 旧版，保留兼容

# 行动项模式：### @xxx 下面的 - [ ] 项目
ACTION_PATTERN = re.compile(r'^### @(\w+)\s*$')
TODO_PATTERN = re.compile(r'^- \[ \] (.+)$')
DONE_PATTERN = re.compile(r'^- \[x\] (.+)$', re.IGNORECASE)

def load_state():
    """加载上次扫描状态"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"lastScan": 0, "processed": []}

def save_state(state):
    """保存扫描状态"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def parse_meeting_file(filepath):
    """解析单个会议文件，提取行动项"""
    content = filepath.read_text(encoding='utf-8')

    # 归档备份类文件：显式跳过，不做行动项提取
    archive_markers = [
        "类型：存档备份",
        "类型: 存档备份",
        "不进入行动项扫描",
        "忽略自动分发与提醒",
    ]
    if any(marker in content for marker in archive_markers):
        return {}

    lines = content.split('\n')
    
    actions = {
        '北哥': [],
        '凡哥': [],
        'Codex': [],
        'Claude': [],
        '调研': [],
        '设计': [],
    }
    
    current_assignee = None
    
    for line in lines:
        # 检查是否是 ### @xxx 标题
        match = ACTION_PATTERN.match(line)
        if match:
            assignee = match.group(1)
            current_assignee = assignee
            continue
        
        # 检查是否是未完成的待办
        if current_assignee:
            todo_match = TODO_PATTERN.match(line)
            if todo_match:
                task = todo_match.group(1).strip()
                if current_assignee in actions:
                    actions[current_assignee].append(task)
                else:
                    actions[current_assignee] = [task]
            
            # 空行或其他标题结束当前 assignee
            if line.strip() == '' or line.startswith('#'):
                if not ACTION_PATTERN.match(line):
                    current_assignee = None
    
    return actions

def extract_date_from_filename(filename):
    """从文件名提取实际会议日期
    
    支持格式：
    - 2026-03-18 - xxx.md (今天新建的)
    - 2026-03-18 2019-07-11T040357Z - xxx.md (今天处理的旧录音，实际日期是 2019)
    - 2019-07-11T040357Z - xxx.md (旧格式)
    """
    import re
    
    # 匹配 ISO 日期时间格式 (YYYY-MM-DDTHH:MM:SSZ)
    iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})T\d{2}', filename)
    if iso_match:
        year, month, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        return datetime(year, month, day)
    
    # 匹配简单日期格式 (YYYY-MM-DD)
    date_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', filename)
    if date_match:
        year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        return datetime(year, month, day)
    
    return None


def scan_meetings(hours=24, scan_all=False):
    """扫描会议笔记"""
    if not MEETINGS_DIR.exists():
        print(f"会议目录不存在: {MEETINGS_DIR}")
        return {}
    
    cutoff = datetime.now() - timedelta(hours=hours)
    all_actions = {}
    
    for filepath in MEETINGS_DIR.glob("*.md"):
        # 跳过模板目录
        if "templates" in str(filepath):
            continue
        
        # 优先从文件名提取实际会议日期
        actual_date = extract_date_from_filename(filepath.name)
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        
        # 如果文件名有日期，用它判断；否则用 mtime
        effective_date = actual_date if actual_date else mtime
        
        if not scan_all and effective_date < cutoff:
            continue
        
        actions = parse_meeting_file(filepath)
        
        # 只记录有行动项的文件
        has_actions = any(len(v) > 0 for v in actions.values())
        if has_actions:
            all_actions[filepath.name] = {
                'path': str(filepath),
                'modified': mtime.isoformat(),
                'actions': actions
            }
    
    return all_actions

def format_output(all_actions):
    """格式化输出"""
    if not all_actions:
        print("没有找到新的行动项。")
        return
    
    output = []
    
    # 按 assignee 聚合
    by_assignee = {}
    for filename, data in all_actions.items():
        for assignee, tasks in data['actions'].items():
            if tasks:
                if assignee not in by_assignee:
                    by_assignee[assignee] = []
                for task in tasks:
                    by_assignee[assignee].append({
                        'task': task,
                        'source': filename
                    })
    
    # 格式化
    print("\n📋 **会议行动项扫描结果**\n")
    
    for assignee, items in by_assignee.items():
        if not items:
            continue
        
        emoji = {
            '北哥': '👤',
            '凡哥': '🦊',
            'Codex': '💻',
            'Claude': '🤖',
            '调研': '🔍',
            '设计': '🎨',
        }.get(assignee, '📌')
        
        print(f"### {emoji} @{assignee}")
        for item in items:
            print(f"- [ ] {item['task']}")
            print(f"  _(来源: {item['source']})_")
        print()
    
    # 返回结构化数据供后续处理
    return by_assignee

def main():
    parser = argparse.ArgumentParser(description='扫描会议笔记行动项')
    parser.add_argument('--hours', type=int, default=24, help='扫描最近 N 小时')
    parser.add_argument('--all', action='store_true', help='扫描所有文件')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式')
    parser.add_argument('--only-new', action='store_true', help='只输出新发现的行动项（去重）')
    args = parser.parse_args()
    
    db = get_db()
    all_actions = scan_meetings(hours=args.hours, scan_all=args.all)
    
    if args.json:
        print(json.dumps(all_actions, indent=2, ensure_ascii=False))
        return
    
    # 存入数据库，并记录新增的
    new_items = []
    for filename, data in all_actions.items():
        file_path = data['path']
        action_count = 0
        
        for assignee, tasks in data['actions'].items():
            for task in tasks:
                is_new = db.add_action_item(
                    source_type='meeting_note',
                    source_path=file_path,
                    assignee=f"@{assignee}",
                    content=task,
                    skip_if_exists=True,
                )
                if is_new:
                    new_items.append({
                        'assignee': assignee,
                        'task': task,
                        'source': filename,
                    })
                    action_count += 1
        
        # 更新会议笔记记录
        db.update_meeting_note(
            file_path=file_path,
            title=filename,
            action_items_count=action_count,
        )
    
    # 只输出新发现的行动项
    if args.only_new or True:  # 默认只输出新的
        if not new_items:
            print("没有新的行动项。")
            return
        
        # 按 assignee 聚合
        by_assignee = {}
        for item in new_items:
            assignee = item['assignee']
            if assignee not in by_assignee:
                by_assignee[assignee] = []
            by_assignee[assignee].append(item)
        
        print("\n📋 **新发现的会议行动项**\n")
        
        for assignee, items in by_assignee.items():
            emoji = {
                '北哥': '👤',
                '凡哥': '🦊',
                'Codex': '💻',
                'Claude': '🤖',
                '调研': '🔍',
                '设计': '🎨',
            }.get(assignee, '📌')
            
            print(f"### {emoji} @{assignee}")
            for item in items:
                print(f"- [ ] {item['task']}")
                print(f"  _(来源: {item['source']})_")
            print()
        
        print(f"共发现 {len(new_items)} 个新行动项。")
    else:
        format_output(all_actions)


if __name__ == '__main__':
    main()
