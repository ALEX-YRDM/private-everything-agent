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

        -- 提示词模板
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            content     TEXT NOT NULL,
            category    TEXT DEFAULT '通用',
            sort_order  INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 全局设置（键值存储，用于保存全局禁用工具等）
        CREATE TABLE IF NOT EXISTS global_settings (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Provider API 密钥表（每类服务商一个 Key，含模型列表）
        CREATE TABLE IF NOT EXISTS provider_keys (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            provider     TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            api_key      TEXT,
            api_base     TEXT,
            models       TEXT DEFAULT '[]',
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

        -- MCP 服务器配置表（支持热插拔）
        -- command/args 对应标准 MCP JSON 格式：{"command": "npx", "args": [...]}
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            transport    TEXT NOT NULL DEFAULT 'stdio',
            command      TEXT,
            args         TEXT DEFAULT '[]',
            url          TEXT,
            env          TEXT DEFAULT '{}',
            enabled      INTEGER DEFAULT 1,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 系统技能启用状态（只存禁用项，不在表中 = 默认启用）
        CREATE TABLE IF NOT EXISTS skill_configs (
            name       TEXT PRIMARY KEY,
            enabled    INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await _db.commit()

    # 迁移：旧库可能缺少 models 列
    try:
        await _db.execute("ALTER TABLE provider_keys ADD COLUMN models TEXT DEFAULT '[]'")
        await _db.commit()
        logger.info("已迁移 provider_keys 表：添加 models 列")
    except Exception:
        pass  # 列已存在，忽略

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

    def _parse_provider_models(self, row: dict) -> dict:
        """将 models JSON 字段反序列化为列表。"""
        try:
            row["models"] = json.loads(row.get("models") or "[]")
        except Exception:
            row["models"] = []
        return row

    async def list_provider_keys(self) -> list[dict]:
        rows = await self.fetch_all("SELECT * FROM provider_keys ORDER BY provider ASC")
        return [self._parse_provider_models(r) for r in rows]

    async def get_provider_key(self, provider: str) -> dict | None:
        row = await self.fetch_one(
            "SELECT * FROM provider_keys WHERE provider = ?", (provider,)
        )
        return self._parse_provider_models(row) if row else None

    async def upsert_provider_key(
        self,
        provider: str,
        display_name: str,
        api_key: str | None,
        api_base: str | None,
        models: list | None = None,
    ) -> dict:
        existing = await self.get_provider_key(provider)
        # 未提供 models 时保留原有列表
        if models is None:
            models = existing["models"] if existing else []
        models_json = json.dumps(models, ensure_ascii=False)
        # 未提供 api_key 时保留原有 key（传 None 且有旧值则不覆盖）
        if api_key is None and existing and existing.get("api_key"):
            api_key_val = existing["api_key"]
        else:
            api_key_val = api_key or None
        await self.execute(
            """INSERT INTO provider_keys (provider, display_name, api_key, api_base, models)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(provider) DO UPDATE SET
                 display_name = excluded.display_name,
                 api_key      = excluded.api_key,
                 api_base     = excluded.api_base,
                 models       = excluded.models,
                 updated_at   = CURRENT_TIMESTAMP""",
            (provider, display_name, api_key_val, api_base or None, models_json),
        )
        return await self.get_provider_key(provider)

    async def update_provider_models(self, provider: str, models: list) -> dict | None:
        """更新指定 provider 的模型列表（不影响 key）。"""
        models_json = json.dumps(models, ensure_ascii=False)
        cursor = await self.execute(
            "UPDATE provider_keys SET models = ?, updated_at = CURRENT_TIMESTAMP WHERE provider = ?",
            (models_json, provider),
        )
        if cursor.rowcount == 0:
            return None
        return await self.get_provider_key(provider)

    async def delete_provider_key(self, provider: str) -> bool:
        cursor = await self.execute(
            "DELETE FROM provider_keys WHERE provider = ?", (provider,)
        )
        return cursor.rowcount > 0

    # ── 提示词模板 ──────────────────────────────────────────────────────────

    async def list_templates(self) -> list[dict]:
        return await self.fetch_all(
            "SELECT * FROM prompt_templates ORDER BY category ASC, sort_order ASC, id ASC"
        )

    async def get_template(self, template_id: int) -> dict | None:
        return await self.fetch_one(
            "SELECT * FROM prompt_templates WHERE id = ?", (template_id,)
        )

    async def create_template(self, name: str, content: str,
                              category: str = "通用", sort_order: int = 0) -> dict:
        cursor = await self.execute(
            "INSERT INTO prompt_templates (name, content, category, sort_order) VALUES (?, ?, ?, ?)",
            (name, content, category, sort_order),
        )
        return await self.get_template(cursor.lastrowid)

    async def update_template(self, template_id: int, **fields) -> dict | None:
        allowed = {"name", "content", "category", "sort_order"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return await self.get_template(template_id)
        updates["updated_at"] = "CURRENT_TIMESTAMP"
        set_clause = ", ".join(
            f"{k} = CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP" else f"{k} = ?"
            for k, v in updates.items()
        )
        values = [v for v in updates.values() if v != "CURRENT_TIMESTAMP"]
        await self.execute(
            f"UPDATE prompt_templates SET {set_clause} WHERE id = ?",
            (*values, template_id),
        )
        return await self.get_template(template_id)

    async def delete_template(self, template_id: int) -> bool:
        cursor = await self.execute(
            "DELETE FROM prompt_templates WHERE id = ?", (template_id,)
        )
        return cursor.rowcount > 0

    # ── 全局设置 ────────────────────────────────────────────────────────────

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.fetch_one("SELECT value FROM global_settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str):
        await self.execute(
            """INSERT INTO global_settings (key, value)
               VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                   updated_at = CURRENT_TIMESTAMP""",
            (key, value),
        )

    # ── MCP 服务器配置 CRUD ─────────────────────────────────────────────────

    def _parse_mcp_server(self, row: dict) -> dict:
        # command 是可执行文件路径（字符串）
        row["command"] = row.get("command") or ""
        try:
            row["args"] = json.loads(row.get("args") or "[]")
        except Exception:
            row["args"] = []
        try:
            row["env"] = json.loads(row.get("env") or "{}")
        except Exception:
            row["env"] = {}
        return row

    async def list_mcp_servers(self) -> list[dict]:
        rows = await self.fetch_all("SELECT * FROM mcp_servers ORDER BY id ASC")
        return [self._parse_mcp_server(r) for r in rows]

    async def get_mcp_server(self, server_id: int) -> dict | None:
        row = await self.fetch_one("SELECT * FROM mcp_servers WHERE id = ?", (server_id,))
        return self._parse_mcp_server(row) if row else None

    async def get_mcp_server_by_name(self, name: str) -> dict | None:
        row = await self.fetch_one("SELECT * FROM mcp_servers WHERE name = ?", (name,))
        return self._parse_mcp_server(row) if row else None

    async def create_mcp_server(
        self,
        name: str,
        display_name: str,
        transport: str = "stdio",
        command: str | None = None,
        args: list | None = None,
        url: str | None = None,
        env: dict | None = None,
        enabled: bool = True,
    ) -> dict:
        cursor = await self.execute(
            """INSERT INTO mcp_servers (name, display_name, transport, command, args, url, env, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name, display_name, transport,
                command or "",
                json.dumps(args or [], ensure_ascii=False),
                url,
                json.dumps(env or {}, ensure_ascii=False),
                1 if enabled else 0,
            ),
        )
        return await self.get_mcp_server(cursor.lastrowid)

    async def update_mcp_server(self, server_id: int, **fields) -> dict | None:
        allowed = {"name", "display_name", "transport", "command", "args", "url", "env", "enabled"}
        updates: dict = {}
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "args":
                updates[k] = json.dumps(v or [], ensure_ascii=False)
            elif k == "env":
                updates[k] = json.dumps(v or {}, ensure_ascii=False)
            elif k == "enabled":
                updates[k] = 1 if v else 0
            else:
                updates[k] = v
        if not updates:
            return await self.get_mcp_server(server_id)
        updates["updated_at"] = "CURRENT_TIMESTAMP"
        set_clause = ", ".join(
            f"{k} = CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP" else f"{k} = ?"
            for k, v in updates.items()
        )
        values = [v for v in updates.values() if v != "CURRENT_TIMESTAMP"]
        await self.execute(
            f"UPDATE mcp_servers SET {set_clause} WHERE id = ?",
            (*values, server_id),
        )
        return await self.get_mcp_server(server_id)

    async def delete_mcp_server(self, server_id: int) -> bool:
        cursor = await self.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))
        return cursor.rowcount > 0

    # ── 会话元数据 ──────────────────────────────────────────────────────────

    async def get_session_metadata(self, session_id: str) -> dict:
        import json as _json
        row = await self.fetch_one("SELECT metadata FROM sessions WHERE id = ?", (session_id,))
        if not row or not row.get("metadata"):
            return {}
        try:
            return _json.loads(row["metadata"])
        except Exception:
            return {}

    async def set_session_metadata(self, session_id: str, metadata: dict):
        import json as _json
        await self.execute(
            "UPDATE sessions SET metadata = ? WHERE id = ?",
            (_json.dumps(metadata, ensure_ascii=False), session_id),
        )

    # ── 系统技能启用状态 ─────────────────────────────────────────────────────

    async def get_disabled_system_skills(self) -> set[str]:
        """返回被禁用的系统技能名称集合。"""
        rows = await self.fetch_all("SELECT name FROM skill_configs WHERE enabled = 0")
        return {r["name"] for r in rows}

    async def list_skill_configs(self) -> list[dict]:
        """返回所有已有配置记录（含 enabled 状态）。"""
        return await self.fetch_all("SELECT name, enabled, updated_at FROM skill_configs ORDER BY name")

    async def set_skill_enabled(self, name: str, enabled: bool) -> None:
        """设置某系统技能的启用状态（upsert）。"""
        await self.execute(
            """INSERT INTO skill_configs (name, enabled, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(name) DO UPDATE SET
                   enabled = excluded.enabled,
                   updated_at = CURRENT_TIMESTAMP""",
            (name, 1 if enabled else 0),
        )
