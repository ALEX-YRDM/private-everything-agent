import aiosqlite
import json
from pathlib import Path
from loguru import logger

DB_PATH = Path("./data/agent.db")

_db: aiosqlite.Connection | None = None


async def init_db():
    """应用启动时初始化表结构。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL DEFAULT '新会话',
            model       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata    JSON DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role            TEXT NOT NULL,
            content         TEXT,
            tool_calls      JSON,
            tool_call_id    TEXT,
            tool_name       TEXT,
            reasoning       TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_consolidated INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS memory_store (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
            memory_md   TEXT DEFAULT '',
            history_md  TEXT DEFAULT '',
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
    """)
    await _db.commit()
    logger.info(f"数据库初始化完成: {DB_PATH}")


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


def get_db_manager() -> "DBManager":
    return DBManager(_db)


class DBManager:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        cursor = await self.db.execute(sql, params)
        await self.db.commit()
        return cursor

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self.db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self.db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_memory(self, session_id: str) -> dict | None:
        return await self.fetch_one(
            "SELECT * FROM memory_store WHERE session_id = ?", (session_id,)
        )

    async def save_memory(self, session_id: str, memory_md: str, history_md: str):
        await self.execute(
            """INSERT INTO memory_store (session_id, memory_md, history_md)
               VALUES (?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
               memory_md = excluded.memory_md,
               history_md = excluded.history_md,
               updated_at = CURRENT_TIMESTAMP""",
            (session_id, memory_md, history_md),
        )

    async def get_unconsolidated_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        return await self.fetch_all(
            """SELECT id, role, content, tool_calls, tool_call_id, tool_name
               FROM messages
               WHERE session_id = ? AND is_consolidated = 0
               ORDER BY id ASC LIMIT ?""",
            (session_id, limit),
        )

    async def mark_consolidated(self, session_id: str, message_ids: list[int]):
        if not message_ids:
            return
        placeholders = ",".join("?" * len(message_ids))
        await self.execute(
            f"UPDATE messages SET is_consolidated = 1 WHERE id IN ({placeholders})",
            tuple(message_ids),
        )
