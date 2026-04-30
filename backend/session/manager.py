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

    async def create_session(self, title: str = "新会话", model: str = None, parent_id: str = None) -> dict:
        session_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO sessions (id, title, model, parent_id) VALUES (?, ?, ?, ?)",
            (session_id, title, model, parent_id),
        )
        return {"id": session_id, "title": title, "model": model, "parent_id": parent_id, "created_at": datetime.now().isoformat()}

    async def get_session(self, session_id: str) -> dict | None:
        return await self.db.fetch_one("SELECT * FROM sessions WHERE id = ?", (session_id,))

    async def list_sessions(self) -> list[dict]:
        """列出主会话（不含 SubAgent 子会话）。"""
        return await self.db.fetch_all(
            "SELECT * FROM sessions WHERE parent_id IS NULL ORDER BY updated_at DESC"
        )

    async def create_subagent_session(
        self,
        parent_session_id: str,
        task_id: str,
        task: str,
    ) -> str:
        """为 SubAgent 创建独立 Session，使用 parent_id 列标记父会话关系。"""
        session = await self.create_session(
            title=f"[子任务] {task[:30]}",
            parent_id=parent_session_id,
        )
        # metadata 中仍保留子任务详情，方便查询
        metadata = {
            "is_subagent": True,
            "subagent_task_id": task_id,
            "subagent_task": task,
        }
        await self.db.set_session_metadata(session["id"], metadata)
        return session["id"]

    async def get_subagent_sessions(self, parent_session_id: str) -> list[dict]:
        """获取某主会话下的所有 SubAgent 子会话。"""
        return await self.db.fetch_all(
            "SELECT * FROM sessions WHERE parent_id = ? ORDER BY created_at ASC",
            (parent_session_id,),
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
                    content = m["content"]
                    # 还原多模态内容：存库时是 JSON 字符串，取出时恢复为数组
                    if isinstance(content, str) and content.startswith('['):
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, list):
                                content = parsed
                        except Exception:
                            pass
                    msg["content"] = content
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
        images: list[str] | None = None,
    ) -> None:
        """原子保存本轮对话到数据库（单次事务）。"""
        statements: list[tuple[str, tuple]] = []

        # 用户消息：有图片时 content 存为 JSON 多模态数组，否则纯文本
        if images:
            parts = [{"type": "text", "text": user_content}]
            for img in images:
                parts.append({"type": "image_url", "image_url": {"url": img}})
            user_content_db = json.dumps(parts, ensure_ascii=False)
        else:
            user_content_db = user_content

        statements.append((
            "INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)",
            (session_id, user_content_db),
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