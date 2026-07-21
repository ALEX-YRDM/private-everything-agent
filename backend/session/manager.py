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

    async def create_session(self, title: str = "新会话", model: str = None,
                             parent_id: str = None, working_dir: str = None) -> dict:
        session_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO sessions (id, title, model, parent_id, working_dir) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, model, parent_id, working_dir),
        )
        return {
            "id": session_id, "title": title, "model": model,
            "parent_id": parent_id, "working_dir": working_dir,
            "created_at": datetime.now().isoformat(),
        }

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

    async def set_working_dir(self, session_id: str, working_dir: str | None) -> bool:
        cursor = await self.db.execute(
            "UPDATE sessions SET working_dir = ? WHERE id = ?",
            (working_dir, session_id),
        )
        return cursor.rowcount > 0

    async def get_trusts(self, session_id: str) -> dict:
        """返回 {paths: [...], commands: [...]}，缺失字段返回空列表。"""
        meta = await self.db.get_session_metadata(session_id)
        return {
            "paths": list(meta.get("trusted_paths") or []),
            "commands": list(meta.get("trusted_commands") or []),
        }

    async def add_trusted_path(self, session_id: str, path: str) -> None:
        meta = await self.db.get_session_metadata(session_id)
        paths = set(meta.get("trusted_paths") or [])
        paths.add(path)
        meta["trusted_paths"] = sorted(paths)
        await self.db.set_session_metadata(session_id, meta)

    async def remove_trusted_path(self, session_id: str, path: str) -> None:
        meta = await self.db.get_session_metadata(session_id)
        paths = set(meta.get("trusted_paths") or [])
        paths.discard(path)
        meta["trusted_paths"] = sorted(paths)
        await self.db.set_session_metadata(session_id, meta)

    async def add_trusted_command(self, session_id: str, prefix: str) -> None:
        meta = await self.db.get_session_metadata(session_id)
        cmds = set(meta.get("trusted_commands") or [])
        cmds.add(prefix)
        meta["trusted_commands"] = sorted(cmds)
        await self.db.set_session_metadata(session_id, meta)

    async def remove_trusted_command(self, session_id: str, prefix: str) -> None:
        meta = await self.db.get_session_metadata(session_id)
        cmds = set(meta.get("trusted_commands") or [])
        cmds.discard(prefix)
        meta["trusted_commands"] = sorted(cmds)
        await self.db.set_session_metadata(session_id, meta)

    def is_path_trusted(self, path: str, trusted_paths: list[str]) -> bool:
        """path 位于任一 trusted_path 子树下则返回 True（含相等）。"""
        from pathlib import Path
        p = Path(path).resolve()
        for t in trusted_paths:
            try:
                tp = Path(t).resolve()
                p.relative_to(tp)
                return True
            except ValueError:
                continue
        return False

    def is_command_trusted(self, command: str, trusted_commands: list[str]) -> bool:
        """command 以任一 trusted_commands 前缀开头则返回 True。"""
        stripped = command.lstrip()
        return any(stripped.startswith(prefix) for prefix in trusted_commands)

    async def get_history(self, session_id: str) -> list[dict]:
        """
        返回用于 LLM 调用的历史消息。
        只返回未被整合的消息，并确保从 user turn 开始对齐。

        同时对孤儿 tool_calls 做修复：若某条 assistant 声明了 tool_calls，
        但后续缺少对应 tool_call_id 的 tool 消息（常见于用户刷新页面/断线时，
        破坏性工具还在等待确认，assistant 消息已落盘但 tool 响应未生成），
        补一条合成的 tool 消息占位，避免 OpenAI 兼容 API 400。
        """
        messages = await self.db.fetch_all(
            """SELECT role, content, tool_calls, tool_call_id, tool_name, files
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

        return self._patch_orphan_tool_calls(result)

    @staticmethod
    def _patch_orphan_tool_calls(messages: list[dict]) -> list[dict]:
        """
        扫描消息序列，对每条声明了 tool_calls 的 assistant，
        校验后续是否为每个 tool_call_id 都有对应 role="tool" 响应；
        缺失的补一条合成占位消息，保证 OpenAI 协议合规。

        真实的响应必然紧跟在 assistant 后面（loop 里每个 tool 完成就 append），
        所以处理策略是：消费完紧邻的 role="tool" 块 → 剩下的 id 就在该块末尾补占位。
        """
        patched: list[dict] = []
        i = 0
        while i < len(messages):
            m = messages[i]
            patched.append(m)
            if m.get("role") == "assistant" and m.get("tool_calls"):
                # 收集本 assistant 声明的所有 pending id → name
                pending: dict[str, str] = {}
                for tc in m["tool_calls"]:
                    tc_id = tc.get("id")
                    if not tc_id:
                        continue
                    fn = tc.get("function") or {}
                    pending[tc_id] = fn.get("name") or tc.get("name") or "unknown"
                # 消费紧邻的 tool 响应
                j = i + 1
                while j < len(messages) and messages[j].get("role") == "tool":
                    patched.append(messages[j])
                    pending.pop(messages[j].get("tool_call_id"), None)
                    j += 1
                # 剩下的 id 补占位（保持声明顺序）
                for tc_id, tc_name in pending.items():
                    patched.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "content": "[连接断开或任务中断，此工具调用未执行]",
                    })
                i = j
            else:
                i += 1
        return patched

    async def get_messages_for_display(self, session_id: str) -> list[dict]:
        """返回用于前端展示的所有消息（包括已整合的）。"""
        return await self.db.fetch_all(
            """SELECT id, role, content, tool_calls, tool_call_id, tool_name, reasoning,
                      input_tokens, output_tokens, files, created_at
               FROM messages WHERE session_id = ? ORDER BY id ASC""",
            (session_id,),
        )

    async def save_turn(
        self,
        session_id: str,
        user_content: str,
        new_messages: list[dict],
        images: list[str] | None = None,
        files: list[dict] | None = None,
    ) -> None:
        """原子保存本轮对话到数据库（单次事务）。"""
        statements: list[tuple[str, tuple]] = []

        # 用户消息：有图片时 content 存为 JSON 多模态数组，否则纯文本
        # 同时将文件内容合并到消息中，以便缓存命中
        if images:
            parts = [{"type": "text", "text": user_content}]
            # 追加文件内容到文本部分
            if files:
                file_content_lines = []
                for file_obj in files:
                    file_name = file_obj.get("name", "unknown")
                    file_text = file_obj.get("parsed_content", "")
                    file_content_lines.append(f"[File: {file_name}]\n{file_text}")
                if file_content_lines:
                    file_section = "\n\n".join(file_content_lines)
                    parts[0]["text"] = parts[0]["text"] + f"\n\n{file_section}"

            for img in images:
                parts.append({"type": "image_url", "image_url": {"url": img}})
            user_content_db = json.dumps(parts, ensure_ascii=False)
        else:
            # 纯文本消息
            user_content_db = user_content
            if files:
                file_content_lines = []
                for file_obj in files:
                    file_name = file_obj.get("name", "unknown")
                    file_text = file_obj.get("parsed_content", "")
                    file_content_lines.append(f"[File: {file_name}]\n{file_text}")
                if file_content_lines:
                    file_section = "\n\n".join(file_content_lines)
                    user_content_db = f"{user_content_db}\n\n{file_section}"

        files_db = json.dumps(files, ensure_ascii=False) if files else None

        statements.append((
            "INSERT INTO messages (session_id, role, content, files) VALUES (?, 'user', ?, ?)",
            (session_id, user_content_db, files_db),
        ))

        for msg in new_messages:
            role = msg["role"]
            content = msg.get("content")
            tool_calls = json.dumps(msg["tool_calls"], ensure_ascii=False) if msg.get("tool_calls") else None
            tool_call_id = msg.get("tool_call_id")
            tool_name = msg.get("name")
            reasoning = msg.get("reasoning") or msg.get("reasoning_content")
            input_tokens = msg.get("input_tokens")
            output_tokens = msg.get("output_tokens")
            statements.append((
                """INSERT INTO messages
                   (session_id, role, content, tool_calls, tool_call_id, tool_name, reasoning,
                    input_tokens, output_tokens)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, role, content, tool_calls, tool_call_id, tool_name, reasoning,
                 input_tokens, output_tokens),
            ))

        statements.append((
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id),
        ))

        await self.db.execute_transaction(statements)