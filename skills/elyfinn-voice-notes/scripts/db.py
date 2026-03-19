#!/usr/bin/env python3
"""
Elyfinn Voice Notes Database

Manages voice memo and meeting notes processing state.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


class ProactiveDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表"""
        self.conn.executescript("""
            -- 语音备忘录表
            CREATE TABLE IF NOT EXISTS voice_memos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT,
                duration_seconds INTEGER,
                recorded_at TEXT,
                discovered_at TEXT,
                processed_at TEXT,
                transcript_path TEXT,
                meeting_note_path TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            );
            
            -- 会议笔记表
            CREATE TABLE IF NOT EXISTS meeting_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                title TEXT,
                meeting_date TEXT,
                last_scanned_at TEXT,
                action_items_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending'
            );
            
            -- 行动项表
            CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,  -- 'voice_memo' or 'meeting_note'
                source_path TEXT NOT NULL,
                assignee TEXT,              -- @北哥, @凡哥, @Codex, etc.
                content TEXT NOT NULL,
                content_hash TEXT UNIQUE,   -- 用于去重
                is_completed INTEGER DEFAULT 0,
                is_notified INTEGER DEFAULT 0,  -- 是否已通知
                discovered_at TEXT,
                completed_at TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_voice_memos_status ON voice_memos(status);
            CREATE INDEX IF NOT EXISTS idx_voice_memos_path ON voice_memos(file_path);
            CREATE INDEX IF NOT EXISTS idx_meeting_notes_path ON meeting_notes(file_path);
            CREATE INDEX IF NOT EXISTS idx_action_items_assignee ON action_items(assignee);
            CREATE INDEX IF NOT EXISTS idx_action_items_completed ON action_items(is_completed);
            CREATE INDEX IF NOT EXISTS idx_action_items_hash ON action_items(content_hash);
        """)
        
        # 添加新列（如果不存在）
        cur = self.conn.execute("PRAGMA table_info(action_items)")
        columns = {row[1] for row in cur.fetchall()}
        
        if "content_hash" not in columns:
            self.conn.execute("ALTER TABLE action_items ADD COLUMN content_hash TEXT")
        if "is_notified" not in columns:
            self.conn.execute("ALTER TABLE action_items ADD COLUMN is_notified INTEGER DEFAULT 0")
        
        self.conn.commit()
    
    # ========== 语音备忘录 ==========
    
    def is_voice_memo_seen(self, file_path: str) -> bool:
        """检查语音备忘录是否已处理。

        视为“已处理/无需再处理”的状态：
        - processed / migrated
        - failed 但属于明确的“永久跳过”(例如超长音频导致无法转录)

        需要重试的状态：pending / processing / failed(可重试)
        """
        cur = self.conn.execute(
            "SELECT status, error_message FROM voice_memos WHERE file_path = ?",
            (file_path,)
        )
        row = cur.fetchone()
        if row is None:
            return False

        status = row[0]
        err = (row[1] or '').strip()

        if status in ('processed', 'migrated'):
            return True

        # 永久跳过：例如超长音频（Gemini 上限）
        if status == 'failed' and err.startswith('Skipped:'):
            return True

        return False
    
    def mark_voice_memo_discovered(
        self,
        file_path: str,
        file_name: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        recorded_at: Optional[str] = None,
    ):
        """标记语音备忘录为已发现"""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO voice_memos (
                file_path, file_name, duration_seconds, recorded_at, discovered_at, status
            ) VALUES (?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(file_path) DO NOTHING
        """, (file_path, file_name, duration_seconds, recorded_at, now))
        self.conn.commit()
    
    def mark_voice_memo_processing(self, file_path: str):
        """标记语音备忘录为处理中"""
        self.conn.execute(
            "UPDATE voice_memos SET status = 'processing' WHERE file_path = ?",
            (file_path,)
        )
        self.conn.commit()
    
    def mark_voice_memo_completed(
        self,
        file_path: str,
        transcript_path: Optional[str] = None,
        meeting_note_path: Optional[str] = None,
    ):
        """标记语音备忘录处理完成"""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            UPDATE voice_memos SET
                processed_at = ?,
                transcript_path = ?,
                meeting_note_path = ?,
                status = 'processed',
                error_message = NULL
            WHERE file_path = ?
        """, (now, transcript_path, meeting_note_path, file_path))
        self.conn.commit()
    
    def mark_voice_memo_failed(self, file_path: str, error_message: str):
        """标记语音备忘录处理失败"""
        self.conn.execute("""
            UPDATE voice_memos SET
                status = 'failed',
                error_message = ?,
                retry_count = COALESCE(retry_count, 0) + 1
            WHERE file_path = ?
        """, (error_message, file_path))
        self.conn.commit()
    
    def get_pending_voice_memos(self, max_retries: int = 3) -> list:
        """获取待处理的语音备忘录"""
        cur = self.conn.execute("""
            SELECT * FROM voice_memos 
            WHERE status = 'pending' 
               OR (status = 'failed' AND retry_count < ?)
            ORDER BY discovered_at ASC
        """, (max_retries,))
        return [dict(row) for row in cur.fetchall()]
    
    # ========== 会议笔记 ==========
    
    def update_meeting_note(
        self,
        file_path: str,
        title: Optional[str] = None,
        meeting_date: Optional[str] = None,
        action_items_count: int = 0,
    ):
        """更新会议笔记记录"""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO meeting_notes (
                file_path, title, meeting_date, last_scanned_at, action_items_count, status
            ) VALUES (?, ?, ?, ?, ?, 'scanned')
            ON CONFLICT(file_path) DO UPDATE SET
                title = COALESCE(excluded.title, title),
                meeting_date = COALESCE(excluded.meeting_date, meeting_date),
                last_scanned_at = excluded.last_scanned_at,
                action_items_count = excluded.action_items_count,
                status = 'scanned'
        """, (file_path, title, meeting_date, now, action_items_count))
        self.conn.commit()
    
    # ========== 行动项 ==========
    
    def _content_hash(self, source_path: str, assignee: str, content: str) -> str:
        """生成行动项的唯一 hash"""
        import hashlib
        key = f"{source_path}|{assignee}|{content}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def is_action_item_seen(self, source_path: str, assignee: str, content: str) -> bool:
        """检查行动项是否已存在（去重）"""
        content_hash = self._content_hash(source_path, assignee, content)
        cur = self.conn.execute(
            "SELECT 1 FROM action_items WHERE content_hash = ?",
            (content_hash,)
        )
        return cur.fetchone() is not None
    
    def add_action_item(
        self,
        source_type: str,
        source_path: str,
        assignee: str,
        content: str,
        skip_if_exists: bool = True,
    ) -> bool:
        """添加行动项，返回是否新增（去重）"""
        content_hash = self._content_hash(source_path, assignee, content)
        
        if skip_if_exists:
            if self.is_action_item_seen(source_path, assignee, content):
                return False
        
        now = datetime.now(timezone.utc).isoformat()
        try:
            self.conn.execute("""
                INSERT INTO action_items (
                    source_type, source_path, assignee, content, content_hash, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (source_type, source_path, assignee, content, content_hash, now))
            self.conn.commit()
            return True
        except Exception:
            return False
    
    def mark_action_item_completed(self, item_id: int):
        """标记行动项完成"""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            UPDATE action_items SET
                is_completed = 1,
                completed_at = ?
            WHERE id = ?
        """, (now, item_id))
        self.conn.commit()
    
    def get_pending_action_items(self, assignee: Optional[str] = None) -> list:
        """获取未完成的行动项"""
        if assignee:
            cur = self.conn.execute("""
                SELECT * FROM action_items 
                WHERE is_completed = 0 AND assignee = ?
                ORDER BY discovered_at DESC
            """, (assignee,))
        else:
            cur = self.conn.execute("""
                SELECT * FROM action_items 
                WHERE is_completed = 0
                ORDER BY discovered_at DESC
            """)
        return [dict(row) for row in cur.fetchall()]
    
    def get_unnotified_action_items(self, assignee: Optional[str] = None) -> list:
        """获取未通知的行动项（用于推送提醒）"""
        if assignee:
            cur = self.conn.execute("""
                SELECT * FROM action_items 
                WHERE is_completed = 0 AND is_notified = 0 AND assignee = ?
                ORDER BY discovered_at ASC
            """, (assignee,))
        else:
            cur = self.conn.execute("""
                SELECT * FROM action_items 
                WHERE is_completed = 0 AND is_notified = 0
                ORDER BY discovered_at ASC
            """)
        return [dict(row) for row in cur.fetchall()]
    
    def mark_action_items_notified(self, item_ids: list):
        """标记行动项为已通知"""
        if not item_ids:
            return
        placeholders = ','.join('?' * len(item_ids))
        self.conn.execute(f"""
            UPDATE action_items SET is_notified = 1 WHERE id IN ({placeholders})
        """, item_ids)
        self.conn.commit()
    
    # ========== 统计 ==========
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {}
        
        # 语音备忘录统计
        cur = self.conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) as processed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM voice_memos
        """)
        row = cur.fetchone()
        stats['voice_memos'] = {
            'total': row['total'] or 0,
            'processed': row['processed'] or 0,
            'failed': row['failed'] or 0,
            'pending': row['pending'] or 0,
        }
        
        # 会议笔记统计
        cur = self.conn.execute("SELECT COUNT(*) as total FROM meeting_notes")
        stats['meeting_notes'] = {'total': cur.fetchone()['total'] or 0}
        
        # 行动项统计
        cur = self.conn.execute("""
            SELECT 
                assignee,
                COUNT(*) as total,
                SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as completed
            FROM action_items
            GROUP BY assignee
        """)
        stats['action_items'] = {
            row['assignee']: {'total': row['total'], 'completed': row['completed']}
            for row in cur.fetchall()
        }
        
        return stats
    
    def close(self):
        self.conn.close()


# ========== 便捷函数 ==========

_db_instance = None

def get_db(data_dir: Optional[Path] = None) -> ProactiveDB:
    """获取数据库实例"""
    global _db_instance
    if _db_instance is None:
        if data_dir is None:
            data_dir = Path.home() / ".openclaw/workspace/data/elyfinn-voice-notes"
        data_dir.mkdir(parents=True, exist_ok=True)
        _db_instance = ProactiveDB(data_dir / "proactive.db")
    return _db_instance


def migrate_from_json(json_path: Path, db: ProactiveDB):
    """从旧的 JSON 状态文件迁移数据"""
    import json
    
    if not json_path.exists():
        return 0
    
    with open(json_path) as f:
        state = json.load(f)
    
    processed = state.get("processed", [])
    migrated = 0
    
    for file_path in processed:
        if not db.is_voice_memo_seen(file_path):
            db.conn.execute("""
                INSERT INTO voice_memos (file_path, status, processed_at)
                VALUES (?, 'migrated', datetime('now'))
            """, (file_path,))
            migrated += 1
    
    db.conn.commit()
    print(f"Migrated {migrated} voice memos from {json_path}")
    return migrated


# ========== CLI ==========

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Voice Notes Database")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--pending", action="store_true", help="Show pending items")
    parser.add_argument("--migrate", action="store_true", help="Migrate from JSON")
    args = parser.parse_args()
    
    db = get_db()
    
    if args.migrate:
        json_path = Path.home() / ".openclaw/workspace/memory/voice-memo-state.json"
        migrate_from_json(json_path, db)
    
    if args.stats:
        stats = db.get_stats()
        print("\n📊 Voice Notes Stats")
        print(f"\n🎙️ Voice Memos:")
        vm = stats['voice_memos']
        print(f"  Total: {vm['total']} | Processed: {vm['processed']} | Failed: {vm['failed']} | Pending: {vm['pending']}")
        
        print(f"\n📝 Meeting Notes: {stats['meeting_notes']['total']}")
        
        print(f"\n✅ Action Items:")
        for assignee, data in stats['action_items'].items():
            print(f"  {assignee}: {data['completed']}/{data['total']} done")
    
    if args.pending:
        pending = db.get_pending_voice_memos()
        print(f"\n⏳ Pending Voice Memos: {len(pending)}")
        for vm in pending[:5]:
            print(f"  - {vm['file_name'] or vm['file_path']}")
    
    db.close()
