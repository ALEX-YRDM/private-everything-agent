import asyncio
from loguru import logger


class MemoryManager:
    """
    双层记忆架构：
    - 会话级 AutoCompact：单个 session 消息过长时，压缩为摘要存入 sessions.summary（会话隔离）
    - 全局极简记忆：跨 session 的用户画像（偏好、技术栈），存入 global_memory.memory_md
    """

    def __init__(self, db_manager, context_window_tokens: int = 65536):
        self.db = db_manager
        self.context_window_tokens = context_window_tokens
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_memory_context_async(self, session_id: str) -> str:
        """读取全局用户画像（跨 session 共享）。"""
        memory = await self.db.get_global_memory()
        return (memory.get("memory_md") or "").strip()

    async def maybe_consolidate(
        self,
        session_id: str,
        provider,
        model: str,
        context_window: int | None = None,
    ) -> bool:
        """检查是否需要压缩，需要则执行。返回 True 表示执行了压缩。"""
        effective_window = context_window or self.context_window_tokens
        last_input_tokens = await self.db.get_last_input_tokens(session_id)
        if last_input_tokens is None or last_input_tokens < effective_window * 0.8:
            return False

        lock = self._locks.setdefault(session_id, asyncio.Lock())
        if lock.locked():
            return False

        async with lock:
            old_messages = await self.db.get_unconsolidated_messages(session_id, limit=50)
            if not old_messages:
                return False

            await self._consolidate_session(session_id, old_messages, provider, model)
            asyncio.create_task(
                self._maybe_update_global_memory(old_messages, provider, model)
            )
            return True

    async def _consolidate_session(
        self,
        session_id: str,
        old_messages: list[dict],
        provider,
        model: str,
    ):
        """会话级 AutoCompact：把早期对话压缩为摘要，存入 sessions.summary。"""
        row = await self.db.fetch_one("SELECT summary FROM sessions WHERE id = ?", (session_id,))
        prev_summary = (row or {}).get("summary") or ""

        prompt = (
            "将以下对话压缩为简洁摘要，供后续对话参考。\n\n"
            + (f"## 已有摘要\n{prev_summary}\n\n" if prev_summary else "")
            + f"## 需压缩的对话\n{self._format_messages(old_messages)}\n\n"
            "要求：保留关键决策、重要结论、用户需求和约束；过滤闲聊和已废弃内容；"
            "中文，结构清晰，不超过500字。\n请调用 save_summary 工具保存。"
        )

        save_tool = {
            "type": "function",
            "function": {
                "name": "save_summary",
                "description": "保存会话压缩摘要",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "压缩后的会话摘要"},
                    },
                    "required": ["summary"],
                },
            },
        }

        for attempt in range(2):
            try:
                response = await provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    tools=[save_tool],
                    model=model,
                )
                if response.has_tool_calls:
                    for tc in response.tool_calls:
                        if tc.name == "save_summary":
                            summary = tc.arguments.get("summary", "")
                            await self.db.execute(
                                "UPDATE sessions SET summary = ? WHERE id = ?",
                                (summary, session_id),
                            )
                            await self.db.mark_consolidated(
                                session_id, [m["id"] for m in old_messages]
                            )
                            logger.info(f"会话 {session_id} AutoCompact 完成")
                            return
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"会话压缩失败，重试: {e}")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"会话压缩最终失败: {e}")

    async def _maybe_update_global_memory(
        self,
        old_messages: list[dict],
        provider,
        model: str,
    ):
        """
        从对话片段中提取用户画像信息，更新全局极简记忆。
        只记录跨会话有价值的偏好/技术栈，具体任务内容不写入。
        失败时静默忽略。
        """
        try:
            existing = await self.db.get_global_memory()
            existing_memory = (existing.get("memory_md") or "").strip()

            prompt = (
                "从以下对话片段中提取值得跨会话记住的用户画像信息"
                "（语言风格偏好、技术栈、工具偏好、明确表达的工作习惯等）。\n"
                "如无新信息，设 unchanged=true 即可，不要更新。\n\n"
                f"## 现有用户画像\n{existing_memory or '（空）'}\n\n"
                f"## 对话片段\n{self._format_messages(old_messages[:20])}\n\n"
                "请调用 update_profile 工具。"
            )

            update_tool = {
                "type": "function",
                "function": {
                    "name": "update_profile",
                    "description": "更新用户画像或标记无需更新",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "memory_md": {"type": "string", "description": "更新后的用户画像（Markdown）"},
                            "unchanged": {"type": "boolean", "description": "无新信息时设为 true"},
                        },
                    },
                },
            }

            response = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                tools=[update_tool],
                model=model,
            )
            if response.has_tool_calls:
                for tc in response.tool_calls:
                    if tc.name == "update_profile" and not tc.arguments.get("unchanged"):
                        new_memory = tc.arguments.get("memory_md", "").strip()
                        if new_memory:
                            await self.db.save_global_memory(memory_md=new_memory)
                            logger.info("全局用户画像已更新")
        except Exception as e:
            logger.warning(f"全局画像更新失败（非致命）: {e}")

    def _format_messages(self, messages: list[dict]) -> str:
        import json as _json
        lines = []
        for m in messages:
            role = m["role"].upper()
            raw = m.get("content", "") or ""
            # 多模态内容（数组或 JSON 字符串）：只保留文字，标注图片数量
            if isinstance(raw, list):
                parts = raw
            elif isinstance(raw, str) and raw.startswith('['):
                try:
                    parts = _json.loads(raw)
                except Exception:
                    parts = None
            else:
                parts = None
            if parts is not None:
                text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
                imgs = sum(1 for p in parts if p.get("type") == "image_url")
                raw = text + (f"（附{imgs}张图片）" if imgs else "")
            lines.append(f"[{role}]: {str(raw)[:2000]}")
        return "\n".join(lines)
