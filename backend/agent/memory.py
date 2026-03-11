import asyncio
from datetime import datetime
from loguru import logger


class MemoryManager:
    """
    双层记忆架构：
    - memory_md: 结构化长期记忆（用户偏好、重要事实）
    - history_md: 时间线日志（[YYYY-MM-DD HH:MM] 格式）

    整合时机：当估算的 prompt token 数超过 context_window_tokens 阈值的 80%。
    整合方式：调用 LLM 自身将旧对话总结写入记忆。
    """

    def __init__(self, db_manager, context_window_tokens: int = 65536):
        self.db = db_manager
        self.context_window_tokens = context_window_tokens
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_memory_context_async(self, session_id: str) -> str:
        memory = await self.db.get_memory(session_id)
        if not memory:
            return ""
        parts = []
        if memory["memory_md"]:
            parts.append(f"### 结构化记忆\n{memory['memory_md']}")
        if memory["history_md"]:
            parts.append(f"### 历史摘要\n{memory['history_md'][-2000:]}")
        return "\n\n".join(parts)

    async def maybe_consolidate(
        self,
        session_id: str,
        messages: list[dict],
        provider,
        model: str,
    ) -> bool:
        """检查是否需要整合记忆，需要则执行。返回 True 表示执行了整合。"""
        estimated_tokens = self._estimate_tokens(messages)
        if estimated_tokens < self.context_window_tokens * 0.8:
            return False

        lock = self._locks.setdefault(session_id, asyncio.Lock())
        if lock.locked():
            return False

        async with lock:
            await self._consolidate(session_id, messages, provider, model)
            return True

    async def _consolidate(self, session_id, messages, provider, model):
        """调用 LLM 整合旧对话到记忆文件。"""
        old_messages = await self.db.get_unconsolidated_messages(session_id, limit=50)
        if not old_messages:
            return

        memory = await self.db.get_memory(session_id) or {}

        consolidation_prompt = f"""
请将以下对话历史整合到记忆系统中，调用 save_memory 工具保存。

## 现有结构化记忆
{memory.get('memory_md', '（无）')}

## 现有历史日志（最近部分）
{memory.get('history_md', '（无）')[-1000:]}

## 需要整合的对话
{self._format_messages_for_consolidation(old_messages)}

请：
1. 更新结构化记忆（保留重要偏好、事实、偏好设置）
2. 追加历史日志条目（格式：[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 一句话摘要）
"""
        save_memory_tool = {
            "type": "function",
            "function": {
                "name": "save_memory",
                "description": "保存整合后的记忆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_md": {"type": "string", "description": "更新后的结构化记忆"},
                        "history_entry": {"type": "string", "description": "新增的历史日志条目"},
                    },
                    "required": ["memory_md", "history_entry"],
                },
            },
        }

        try:
            response = await provider.chat(
                messages=[{"role": "user", "content": consolidation_prompt}],
                tools=[save_memory_tool],
                model=model,
            )

            if response.has_tool_calls:
                for tc in response.tool_calls:
                    if tc.name == "save_memory":
                        existing_history = memory.get("history_md", "")
                        new_history = existing_history + "\n" + tc.arguments.get("history_entry", "")
                        await self.db.save_memory(
                            session_id,
                            memory_md=tc.arguments.get("memory_md", ""),
                            history_md=new_history,
                        )
                        await self.db.mark_consolidated(
                            session_id, [m["id"] for m in old_messages]
                        )
                        logger.info(f"会话 {session_id} 记忆整合完成")
        except Exception as e:
            logger.error(f"记忆整合失败: {e}")

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """粗略估算 token 数（按字符数 / 4 估算）。"""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 4

    def _format_messages_for_consolidation(self, messages: list[dict]) -> str:
        lines = []
        for m in messages:
            role = m["role"].upper()
            content = str(m.get("content", ""))[:500]
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)
