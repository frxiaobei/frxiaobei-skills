#!/usr/bin/env python3
"""
语音备忘录扫描与处理脚本

功能：
1. 扫描 Voice Memos 录音文件
2. 过滤掉正在录制的文件（安全检查）
3. 用 Gemini API 转录
4. AI 生成会议纪要（提取标题、内容、action items）
5. 保存到 Obsidian meetings/ 目录
6. 按 @标签分发任务

数据存储：SQLite (data/proactive-work/proactive.db)
"""

import os
import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# 添加当前目录到 path，以便导入 db 模块
sys.path.insert(0, str(Path(__file__).parent))
from db import get_db, migrate_from_json
from config import load_config, config_exists, get_output_directory, get_recording_source, should_ask_on_uncertain, get_type_label

# Load user config first
USER_CONFIG = load_config()

# Paths from config (user-configurable)
VOICE_MEMOS_DIR = get_recording_source(USER_CONFIG)
VOICE_MEMOS_DB = VOICE_MEMOS_DIR / "CloudRecordings.db"  # Only used if source is Voice Memos
MEETINGS_DIR = get_output_directory(USER_CONFIG)

# Legacy/internal paths
STATE_FILE_LEGACY = Path.home() / ".openclaw/workspace/memory/voice-memo-state.legacy.json"
STATE_FILE = Path.home() / ".openclaw/workspace/memory/voice-memo-state.json"
VOLC_ENV = Path.home() / ".config/volcengine/.env"

# 安全阈值：跳过最近 N 分钟内修改的文件
SAFE_MINUTES = 5
# 最大时长限制：跳过超过 N 秒的文件（Gemini API 限制）
MAX_DURATION_SECONDS = 7200  # 2 hours


def load_state():
    """加载处理状态。

    - 主状态以 SQLite 为准。
    - 若存在旧版 JSON（voice-memo-state.legacy.json），则仅用于一次性迁移。
    - memory/voice-memo-state.json 作为“当前状态快照”保留，不再被重命名。
    """
    db = get_db()

    # 一次性迁移旧数据
    if STATE_FILE_LEGACY.exists():
        migrate_from_json(STATE_FILE_LEGACY, db)
        STATE_FILE_LEGACY.rename(STATE_FILE_LEGACY.with_suffix('.json.migrated'))

    return db


def save_state(state):
    """保存处理状态（现在是 no-op，状态已在 SQLite 中实时更新）"""
    # SQLite 版本不需要显式保存，每次操作都会 commit
    pass


def get_recordings_from_db():
    """从数据库获取录音列表"""
    if not VOICE_MEMOS_DB.exists():
        return []
    
    conn = sqlite3.connect(str(VOICE_MEMOS_DB))
    cursor = conn.cursor()
    
    # 获取所有录音的路径、时长、日期（只处理 >= 1 分钟的）
    cursor.execute("""
        SELECT ZPATH, ZDURATION, ZDATE, ZFLAGS, ZCUSTOMLABEL
        FROM ZCLOUDRECORDING
        WHERE ZDURATION >= 60
        ORDER BY ZDATE DESC
    """)
    
    recordings = []
    for row in cursor.fetchall():
        path, duration, date, flags, label = row
        if path:
            recordings.append({
                'path': path,
                'duration': duration,
                'date': date,
                'flags': flags,
                'label': label
            })
    
    conn.close()
    return recordings


def is_file_safe_to_process(filepath):
    """检查文件是否安全可处理"""
    # 1. 检查文件是否存在
    if not filepath.exists():
        return False
    
    # 2. 检查最后修改时间（跳过最近 5 分钟内修改的）
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
    if datetime.now() - mtime < timedelta(minutes=SAFE_MINUTES):
        return False
    
    # 3. 检查文件是否被 Voice Memos 占用
    try:
        result = subprocess.run(
            ['lsof', str(filepath)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if 'Voice Memos' in result.stdout:
            return False
    except:
        pass
    
    return True


def transcribe_audio(audio_path):
    """使用 Gemini API 转录音频（替代 OpenAI Whisper）"""
    GEMINI_SKILL = Path.home() / ".openclaw/workspace/skills/gemini-transcribe/scripts/transcribe.py"

    if not GEMINI_SKILL.exists():
        raise FileNotFoundError(f"Gemini transcribe skill not found: {GEMINI_SKILL}")
    
    # 准备输出文件
    output_file = Path("/tmp") / f"{audio_path.stem}_transcript.txt"
    
    # 执行转录（Gemini skill 会自动处理 qta 格式转换和 API key）
    result = subprocess.run(
        ['python3', str(GEMINI_SKILL), str(audio_path), '--out', str(output_file)],
        capture_output=True,
        text=True,
        timeout=600  # 10 分钟超时（长音频需要更多时间）
    )
    
    if result.returncode != 0:
        raise Exception(f"Transcription failed: {result.stderr}")
    
    # 读取转录结果
    if output_file.exists():
        with open(output_file) as f:
            text = f.read().strip()
        return text

    raise Exception("Transcription output file not found")


def classify_recording(transcript):
    """分类录音类型
    
    返回: dict with type, confidence, reason, participants, topic
    """
    gemini_query = Path.home() / ".openclaw/workspace/skills/gemini/scripts/gemini_query.py"
    
    # 截取前 3000 字用于分类
    preview = transcript[:3000]
    if len(transcript) > 3000:
        preview += "\n\n[... 后续内容省略 ...]"
    
    # Load classification template
    template = load_template("classification")
    prompt = template.format(transcript_preview=preview)

    try:
        r = subprocess.run(
            ['python3', str(gemini_query), prompt, 'gemini-2.5-flash'],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0:
            response = (r.stdout or '').strip()
            # 解析 JSON
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                response = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                response = response[start:end].strip()
            return json.loads(response)
    except Exception as e:
        print(f"   ⚠️  分类失败: {e}")
    
    # 默认返回 meeting
    return {"type": "meeting", "confidence": 0.5, "reason": "默认分类", "participants": [], "topic": "未知"}


# Type prefix mapping (for filenames) - can be overridden by config
TYPE_PREFIX = USER_CONFIG.get("type_labels", {
    "meeting": "Meeting",
    "keynote": "Keynote",
    "interview": "Interview",
    "customer": "Customer",
    "brainstorm": "Brainstorm",
    "consult": "Consult",
    "note": "Note"
})

# Templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_template(template_name: str) -> str:
    """Load a prompt template from the templates directory."""
    template_path = TEMPLATES_DIR / f"{template_name}.md"
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    raise FileNotFoundError(f"Template not found: {template_path}")


def generate_meeting_notes(transcript, recording_info):
    """根据录音类型生成对应格式的笔记

    流程：
    1. 先分类录音类型
    2. 根据类型选择不同的 prompt 模板
    3. 生成对应格式的笔记
    """

    date_str = datetime.now().strftime('%Y-%m-%d')

    # Prefer a label if exists
    label = (recording_info.get('label') or '').strip()
    base_title = label if label else '语音备忘录'

    gemini_query = Path.home() / ".openclaw/workspace/skills/gemini/scripts/gemini_query.py"

    # Step 1: 分类
    print("   🏷️  分类中...")
    classification = classify_recording(transcript)
    rec_type = classification.get('type', 'meeting')
    confidence = classification.get('confidence', 0.5)
    reason = classification.get('reason', '')
    print(f"   📌 类型: {rec_type} ({TYPE_PREFIX.get(rec_type, '未知')}) | 置信度: {confidence:.0%}")
    print(f"   💡 原因: {reason}")

    # Step 2: Load template and build prompt
    type_prefix = TYPE_PREFIX.get(rec_type, 'Note')
    
    # Load template from file
    template = load_template(rec_type)
    
    # Build prompt with variables
    prompt = template.format(
        date_str=date_str,
        type_prefix=type_prefix,
        transcript=transcript,
        path=recording_info.get('path', ''),
        duration=recording_info.get('duration', 0)
    )

    # Step 3: 调用 Gemini 生成笔记
    ai_md = None
    if gemini_query.exists():
        try:
            r = subprocess.run(
                ['python3', str(gemini_query), prompt, 'gemini-2.5-flash'],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if r.returncode == 0:
                ai_md = (r.stdout or '').strip()
            else:
                raise Exception((r.stderr or r.stdout or '').strip() or f"gemini_query failed code={r.returncode}")
        except Exception as e:
            # Fallback to a minimal note if Gemini fails
            ai_md = None

    if not ai_md:
        title = f"{date_str}-{type_prefix}-{base_title}"
        notes = f"""# {date_str} {type_prefix}-{base_title}

**来源**: 语音备忘录 {recording_info.get('path')}
**时长**: {recording_info.get('duration', 0):.1f} 秒
**日期**: {date_str}
**类型**: {type_prefix} (confidence: {confidence:.0%})

## 内容

（AI 生成失败，待整理）

---

<details>
<summary>📝 原始转录（点击展开）</summary>

{transcript}

</details>
"""
        return title, notes, classification

    # Extract title from first heading
    first_line = ai_md.splitlines()[0].strip() if ai_md.splitlines() else ''
    title = f"{date_str}-{type_prefix}-{base_title}"
    if first_line.startswith('#'):
        # Strip leading # and take up to ~80 chars for filename
        t = first_line.lstrip('#').strip()
        if t:
            title = t[:80]

    # Append source + transcript at bottom for traceability
    meta_block = f"""

---

**来源**: 语音备忘录 {recording_info.get('path')}
**时长**: {recording_info.get('duration', 0):.1f} 秒
**类型**: {type_prefix} (confidence: {confidence:.0%}, reason: {reason})

<details>
<summary>📝 原始转录（点击展开）</summary>

{transcript}

</details>
""".strip("\n")

    notes = ai_md.strip() + "\n\n" + meta_block + "\n"
    return title, notes, classification


def extract_action_items(notes):
    """提取 action items"""
    # 简化版：查找 @标签
    # 后续可以用 AI 增强
    action_items = []
    
    for line in notes.split('\n'):
        if '@' in line and '[ ]' in line:
            action_items.append(line.strip())
    
    return action_items


def save_meeting_notes(title, notes):
    """保存会议纪要到 Obsidian"""
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名（移除特殊字符）
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    filepath = MEETINGS_DIR / f"{safe_title}.md"
    
    # 避免覆盖，如果文件已存在则加数字后缀
    counter = 1
    while filepath.exists():
        filepath = MEETINGS_DIR / f"{safe_title}-{counter}.md"
        counter += 1
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(notes)
    
    return filepath


def main():
    """主流程"""
    print("🎙️ 扫描语音备忘录...")
    
    # 加载状态（SQLite）
    db = load_state()
    
    # 获取录音列表
    recordings = get_recordings_from_db()
    print(f"📊 数据库中共有 {len(recordings)} 个录音")
    
    # 处理新录音
    new_count = 0
    for rec in recordings:
        filepath = VOICE_MEMOS_DIR / rec['path']
        file_path_str = str(filepath)
        
        # 跳过已处理的
        if db.is_voice_memo_seen(file_path_str):
            continue
        
        # 跳过超长录音（>2小时）
        if rec.get('duration', 0) > MAX_DURATION_SECONDS:
            print(f"⏸️  跳过（超长 {rec['duration']:.0f}s > {MAX_DURATION_SECONDS}s）: {rec['path']}")
            # 标记为跳过，避免重复提示
            db.mark_voice_memo_discovered(
                file_path=file_path_str,
                file_name=rec.get('label') or rec['path'],
                duration_seconds=int(rec.get('duration', 0)),
                recorded_at=rec.get('date'),
            )
            db.mark_voice_memo_failed(file_path_str, f"Skipped: duration {rec['duration']:.0f}s exceeds limit {MAX_DURATION_SECONDS}s")
            continue
        
        # 安全检查
        if not is_file_safe_to_process(filepath):
            print(f"⏸️  跳过（不安全）: {rec['path']}")
            continue
        
        print(f"\n🎯 处理: {rec['path']}")
        print(f"   时长: {rec['duration']:.1f}s")
        
        # 标记为发现
        db.mark_voice_memo_discovered(
            file_path=file_path_str,
            file_name=rec.get('label') or rec['path'],
            duration_seconds=int(rec.get('duration', 0)),
            recorded_at=rec.get('date'),
        )
        
        # 标记为处理中
        db.mark_voice_memo_processing(file_path_str)
        
        try:
            # 转录
            print("   📝 转录中...")
            transcript = transcribe_audio(filepath)
            
            # 生成笔记（根据类型自动选择格式）
            print("   📋 生成笔记...")
            title, notes, classification = generate_meeting_notes(transcript, rec)
            rec_type = classification.get('type', 'meeting')
            
            # 保存
            print("   💾 保存到 Obsidian...")
            saved_path = save_meeting_notes(title, notes)
            print(f"   ✅ 已保存: {saved_path}")
            
            # 提取 action items 并存入数据库
            action_items = extract_action_items(notes)
            if action_items:
                print(f"   📌 发现 {len(action_items)} 个 action items")
                for item in action_items:
                    # 提取 assignee
                    import re
                    assignee_match = re.search(r'@(\w+)', item)
                    assignee = f"@{assignee_match.group(1)}" if assignee_match else "@凡哥"
                    db.add_action_item(
                        source_type='voice_memo',
                        source_path=file_path_str,
                        assignee=assignee,
                        content=item,
                    )

            # 按 @ 标签分发（写入任务注册表 / reminder registry / cron 文件）
            try:
                dispatcher = Path.home() / ".openclaw/workspace/skills/proactive-work/scripts/scan-and-dispatch.sh"
                if dispatcher.exists():
                    # 只额外扫描这一个新生成的会议纪要文件，减少误触发
                    subprocess.run(
                        [
                            'bash',
                            str(dispatcher),
                            '--since-hours',
                            '6',
                            '--root',
                            str(saved_path),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    print("   🚚 已完成任务分发（按 @ 标签）")
            except subprocess.CalledProcessError as e:
                err = (e.stderr or e.stdout or '').strip()
                print(f"   ⚠️  分发失败: {err}")
            except Exception as e:
                print(f"   ⚠️  分发失败: {e}")

            # 标记为已完成
            db.mark_voice_memo_completed(
                file_path=file_path_str,
                meeting_note_path=str(saved_path),
            )
            new_count += 1
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            db.mark_voice_memo_failed(file_path_str, str(e))
            continue
    
    # 打印统计
    stats = db.get_stats()
    vm_stats = stats['voice_memos']
    print(f"\n✅ 扫描完成！处理了 {new_count} 个新录音")
    print(f"📊 总计: {vm_stats['total']} | 已处理: {vm_stats['processed']} | 失败: {vm_stats['failed']}")


if __name__ == "__main__":
    main()
