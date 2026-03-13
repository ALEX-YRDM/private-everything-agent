import uuid
import json
from datetime import datetime


class SessionManager:
    """
    基于 SQLite 的会话管理器。
    """

    def __init__(self, db_manager, max_history_messages: int = 200):
        self.db = db_manager
        self.max_history = max_history_messages

    async def create_session(self, title: str = "新会话", model: str = None) -> dict:
        session_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO sessions (id, title, model) VALUES (?, ?, ?)",
            (session_id, title, model),
        )
        return {"id": session_id, "title": title, "model": model, "created_at": datetime.now().isoformat()}

    async def get_session(self, session_id: str) -> dict | None:
        return await self.db.fetch_one("SELECT * FROM sessions WHERE id = ?", (session_id,))

    async def list_sessions(self) -> list[dict]:
        return await self.db.fetch_all(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        )

    async def delete_session(self, session_id: str) -> bool:
        cursor = await self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    async def update_title(self, session_id: str, title: str) -> bool:
        cursor = await self.db.execute(
            "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
        )
        return cursor.rowcount > 0

    async def get_history(self, session_id: str) -> list[dict]:
        """
        返回用于 LLM 调用的历史消息。
        只返回未被整合的消息，并确保从 user turn 开始对齐。
        """
        messages = await self.db.fetch_all(
            """SELECT role, content, tool_calls, tool_call_id, tool_name
               FROM messages
               WHERE session_id = ? AND is_consolidated = 0
               ORDER BY id ASC
               LIMIT ?""",
            (session_id, self.max_history),
        )

        result = []
        found_user = False
        for m in messages:
            if m["role"] == "user":
                found_user = True
            if found_user:
                msg: dict = {"role": m["role"]}
                if m["content"] is not None:
                    msg["content"] = m["content"]
                if m["tool_calls"]:
                    msg["tool_calls"] = json.loads(m["tool_calls"])
                if m["tool_call_id"]:
                    msg["tool_call_id"] = m["tool_call_id"]
                    msg["name"] = m["tool_name"]
                result.append(msg)
        return result

    async def get_messages_for_display(self, session_id: str) -> list[dict]:
        """返回用于前端展示的所有消息（包括已整合的）。"""
        return await self.db.fetch_all(
            """SELECT id, role, content, tool_calls, tool_call_id, tool_name, reasoning, created_at
               FROM messages WHERE session_id = ? ORDER BY id ASC""",
            (session_id,),
        )

    async def save_turn(
        self,
        session_id: str,
        user_content: str,
        new_messages: list[dict],
    ) -> None:
        """原子保存本轮对话到数据库（单次事务）。"""
        statements: list[tuple[str, tuple]] = []

        statements.append((
            "INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)",
            (session_id, user_content),
        ))

        for msg in new_messages:
            role = msg["role"]
            content = msg.get("content")
            tool_calls = json.dumps(msg["tool_calls"], ensure_ascii=False) if msg.get("tool_calls") else None
            tool_call_id = msg.get("tool_call_id")
            tool_name = msg.get("name")
            reasoning = msg.get("reasoning")
            statements.append((
                """INSERT INTO messages
                   (session_id, role, content, tool_calls, tool_call_id, tool_name, reasoning)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, role, content, tool_calls, tool_call_id, tool_name, reasoning),
            ))

        statements.append((
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id),
        ))

        await self.db.execute_transaction(statements)
