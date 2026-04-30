import asyncio
from datetime import datetime
from loguru import logger


class MemoryManager:
    """
    全局记忆架构（跨 session 共享）：
    - memory_md: 结构化长期记忆（用户偏好、重要事实）
    - history_md: 时间线日志（[YYYY-MM-DD HH:MM] 格式）

    整合时机：当估算的 prompt token 数超过 context_window_tokens 阈值的 80%。
    整合方式：调用 LLM 自身将旧对话总结写入全局记忆（global_memory 表）。
    """

    def __init__(self, db_manager, context_window_tokens: int = 65536):
        self.db = db_manager
        self.context_window_tokens = context_window_tokens
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_memory_context_async(self, session_id: str) -> str:
        """读取全局记忆（不依赖 session_id，所有会话共享同一份记忆）。"""
        memory = await self.db.get_global_memory()
        if not memory:
            return ""
        parts = []
        if memory.get("memory_md"):
            parts.append(f"### 结构化记忆\n{memory['memory_md']}")
        if memory.get("history_md"):
            parts.append(f"### 历史摘要\n{memory['history_md']}")
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
        """调用 LLM 整合旧对话到全局记忆。失败时最多重试一次。"""
        old_messages = await self.db.get_unconsolidated_messages(session_id, limit=50)
        if not old_messages:
            return

        memory = await self.db.get_global_memory()

        consolidation_prompt = f"""
请将以下对话历史整合到记忆系统中，调用 save_memory 工具保存。

## 现有结构化记忆
{memory.get('memory_md', '（无）')}

## 现有历史日志（最近部分）
{memory.get('history_md', '（无）')[-1000:]}

## 需要整合的对话
{self._format_messages_for_consolidation(old_messages)}

---

## 整合要求

**memory_md**（结构化记忆，使用以下固定格式，无相关内容的节可省略）：
```
## 用户偏好
- [语言风格、工作习惯、偏好设置等]

## 技术栈与环境
- [项目语言、框架、工具链、系统环境等]

## 重要事实
- [用户告知的关键约束、项目背景、特殊要求等]

## 进行中的项目
- [项目名]：[当前状态 / 目标 / 未完成事项]
```

**整合规则**：
1. memory_md 完整重写（合并旧记忆 + 从对话中提取新信息），不丢失已有重要内容
2. 只记录有实质价值的信息：用户偏好、重要决策、项目背景；过滤闲聊和重复确认
3. history_entry 只写本次新增的**一条**，格式：`[{datetime.now().strftime('%Y-%m-%d %H:%M')}] <20字以内的一句话摘要>`
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

        for attempt in range(2):
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
                            await self.db.save_global_memory(
                                memory_md=tc.arguments.get("memory_md", ""),
                                history_md=new_history,
                            )
                            await self.db.mark_consolidated(
                                session_id, [m["id"] for m in old_messages]
                            )
                            logger.info(f"会话 {session_id} 记忆整合完成（全局）")
                            return
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"记忆整合失败，2s 后重试: {e}")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"记忆整合最终失败: {e}")

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """估算 token 数，针对中文字符做特殊处理（1 CJK ≈ 1 token，其余 4 chars ≈ 1 token）。"""
        total = 0
        for m in messages:
            content = m.get("content") or ""
            if isinstance(content, list):
                # 处理多模态内容，区分文本和图像
                text_content = ""
                image_count = 0
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            text_content += part.get("text", "")
                        elif part.get("type") == "image_url":
                            image_count += 1
                    else:
                        text_content += str(part)
                # 图像按固定token数计算（每张图约1000 token，根据不同模型可能有差异，这里取保守值）
                total += image_count * 1000
                content = text_content
            # CJK 字符（中日韩）每个约 1 token
            cjk = sum(1 for c in content if "\u4e00" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f")
            other = len(content) - cjk
            total += cjk + other // 4
            # tool_calls 单独计算
            if m.get("tool_calls"):
                tc_str = str(m["tool_calls"])
                total += len(tc_str) // 4 + 20
            total += 10  # 每条消息的结构开销
        return total

    def _format_messages_for_consolidation(self, messages: list[dict]) -> str:
        lines = []
        for m in messages:
            role = m["role"].upper()
            content = str(m.get("content", ""))[:2000]
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)
