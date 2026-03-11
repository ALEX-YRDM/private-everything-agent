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

        -- 模型配置表
        CREATE TABLE IF NOT EXISTS model_configs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            model_id    TEXT NOT NULL,
            api_key     TEXT,
            api_base    TEXT,
            temperature REAL DEFAULT 0.1,
            max_tokens  INTEGER DEFAULT 4096,
            is_default  INTEGER DEFAULT 0,
            enabled     INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Provider API 密钥表（每类服务商一个 Key）
        CREATE TABLE IF NOT EXISTS provider_keys (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            provider     TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            api_key      TEXT,
            api_base     TEXT,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 定时任务表
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            cron_expr   TEXT NOT NULL,
            prompt      TEXT NOT NULL,
            model_id    TEXT,
            enabled     INTEGER DEFAULT 1,
            last_run_at TIMESTAMP,
            last_status TEXT,
            session_id  TEXT REFERENCES sessions(id) ON DELETE SET NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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

    # ── 模型配置 CRUD ──────────────────────────────────────────────────────────

    async def list_model_configs(self) -> list[dict]:
        return await self.fetch_all("SELECT * FROM model_configs ORDER BY id ASC")

    async def get_model_config(self, config_id: int) -> dict | None:
        return await self.fetch_one("SELECT * FROM model_configs WHERE id = ?", (config_id,))

    async def get_default_model_config(self) -> dict | None:
        return await self.fetch_one(
            "SELECT * FROM model_configs WHERE is_default = 1 AND enabled = 1 LIMIT 1"
        )

    async def create_model_config(self, name: str, model_id: str, api_key: str | None,
                                   api_base: str | None, temperature: float, max_tokens: int) -> dict:
        cursor = await self.execute(
            """INSERT INTO model_configs (name, model_id, api_key, api_base, temperature, max_tokens)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, model_id, api_key, api_base, temperature, max_tokens),
        )
        return await self.get_model_config(cursor.lastrowid)

    async def update_model_config(self, config_id: int, **fields) -> dict | None:
        allowed = {"name", "model_id", "api_key", "api_base", "temperature", "max_tokens", "enabled"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return await self.get_model_config(config_id)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        await self.execute(
            f"UPDATE model_configs SET {set_clause} WHERE id = ?",
            (*updates.values(), config_id),
        )
        return await self.get_model_config(config_id)

    async def delete_model_config(self, config_id: int) -> bool:
        cursor = await self.execute("DELETE FROM model_configs WHERE id = ?", (config_id,))
        return cursor.rowcount > 0

    async def set_default_model_config(self, config_id: int):
        """将指定配置设为默认，同时取消其他配置的默认状态。"""
        await self.execute("UPDATE model_configs SET is_default = 0")
        await self.execute("UPDATE model_configs SET is_default = 1 WHERE id = ?", (config_id,))

    # ── 定时任务 CRUD ──────────────────────────────────────────────────────────

    async def list_tasks(self) -> list[dict]:
        return await self.fetch_all("SELECT * FROM scheduled_tasks ORDER BY id ASC")

    async def get_task(self, task_id: int) -> dict | None:
        return await self.fetch_one("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))

    async def create_task(self, name: str, cron_expr: str, prompt: str,
                          model_id: str | None = None) -> dict:
        cursor = await self.execute(
            "INSERT INTO scheduled_tasks (name, cron_expr, prompt, model_id) VALUES (?, ?, ?, ?)",
            (name, cron_expr, prompt, model_id),
        )
        return await self.get_task(cursor.lastrowid)

    async def update_task(self, task_id: int, **fields) -> dict | None:
        allowed = {"name", "cron_expr", "prompt", "model_id", "enabled"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return await self.get_task(task_id)
        updates["updated_at"] = "CURRENT_TIMESTAMP"
        set_clause = ", ".join(
            f"{k} = CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP" else f"{k} = ?"
            for k, v in updates.items()
        )
        values = [v for v in updates.values() if v != "CURRENT_TIMESTAMP"]
        await self.execute(
            f"UPDATE scheduled_tasks SET {set_clause} WHERE id = ?",
            (*values, task_id),
        )
        return await self.get_task(task_id)

    async def delete_task(self, task_id: int) -> bool:
        cursor = await self.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0

    async def update_task_run_status(self, task_id: int, status: str, session_id: str | None = None):
        await self.execute(
            """UPDATE scheduled_tasks
               SET last_run_at = CURRENT_TIMESTAMP, last_status = ?, session_id = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, session_id, task_id),
        )

    # ── Provider API Keys ──────────────────────────────────────────────────

    async def list_provider_keys(self) -> list[dict]:
        return await self.fetch_all(
            "SELECT * FROM provider_keys ORDER BY provider ASC"
        )

    async def get_provider_key(self, provider: str) -> dict | None:
        return await self.fetch_one(
            "SELECT * FROM provider_keys WHERE provider = ?", (provider,)
        )

    async def upsert_provider_key(
        self, provider: str, display_name: str,
        api_key: str | None, api_base: str | None
    ) -> dict:
        await self.execute(
            """INSERT INTO provider_keys (provider, display_name, api_key, api_base)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(provider) DO UPDATE SET
                 display_name = excluded.display_name,
                 api_key      = excluded.api_key,
                 api_base     = excluded.api_base,
                 updated_at   = CURRENT_TIMESTAMP""",
            (provider, display_name, api_key or None, api_base or None),
        )
        return await self.get_provider_key(provider)

    async def delete_provider_key(self, provider: str) -> bool:
        cursor = await self.execute(
            "DELETE FROM provider_keys WHERE provider = ?", (provider,)
        )
        return cursor.rowcount > 0
