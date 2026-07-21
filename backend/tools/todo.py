"""
todo_write / todo_read 工具组：让 Agent 维护会话级 Todo 列表。

- 存储位置：session_metadata["todos"] = [{id, content, status}]
- Agent 每次 todo_write 会**整体覆盖**（不是增量），符合"list state" 的语义
- 每次写入后通过 stream_callback 广播 todos_update 事件，前端实时更新

注意：SubAgent 不使用这组工具，避免"todo 谁的" 的语义混乱。
"""
from __future__ import annotations

import json
from typing import Any

from .base import StreamingTool, Tool
from .context import ToolContext


TODO_STATUSES = {"pending", "in_progress", "completed"}


def _normalize_todos(items: list[dict]) -> list[dict]:
    """校验 + 归一化 todos。"""
    out: list[dict] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        status = str(item.get("status") or "pending").lower()
        if status not in TODO_STATUSES:
            status = "pending"
        tid = str(item.get("id") or f"t{i + 1}")
        # id 冲突时加后缀
        while tid in seen_ids:
            tid = f"{tid}_"
        seen_ids.add(tid)
        out.append({"id": tid, "content": content, "status": status})
    return out


class TodoWriteTool(StreamingTool):
    """
    覆盖式写入本会话的 todo 列表；前端会实时看到变化。
    典型用法：在多步任务开始时列出计划、执行过程中标记 in_progress、
    完成时置 completed；用户能一眼看到进度。
    """

    def __init__(self, db_manager):
        self._db = db_manager

    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return (
            "覆盖式写入当前会话的 todo 列表，前端右上角面板实时刷新。\n\n"
            "**使用时机：**\n"
            "- 多步任务开始时，一次性列出全部步骤\n"
            "- 每完成 / 开始一个步骤时，重新调用写入最新状态\n"
            "- 状态取值：pending（待办）/ in_progress（进行中）/ completed（完成）\n\n"
            "**注意：**\n"
            "- 每次调用会**整体覆盖** todos；缺失的项会被删除\n"
            "- 若整轮任务只有一步或纯问答，不需要用这个工具"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "完整的 todo 列表（会覆盖旧列表）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "唯一 id，缺省自动生成"},
                            "content": {"type": "string", "description": "简短的一句话（20 字以内更好）"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content"],
                    },
                },
            },
            "required": ["todos"],
        }

    async def execute_streaming(
        self,
        stream_callback,
        todos: list[dict],
        _ctx: ToolContext | None = None,
    ) -> str:
        if _ctx is None or not _ctx.session_id:
            return "[错误] 未拿到 session_id，无法保存 todos"
        normalized = _normalize_todos(todos)
        meta = await self._db.get_session_metadata(_ctx.session_id)
        meta["todos"] = normalized
        await self._db.set_session_metadata(_ctx.session_id, meta)

        # 广播给前端
        stream_callback({
            "type": "todos_update",
            "session_id": _ctx.session_id,
            "todos": normalized,
        })

        summary = [
            f"- [{'x' if t['status'] == 'completed' else ' '}] {t['content']}"
            + (f"  ({t['status']})" if t["status"] == "in_progress" else "")
            for t in normalized
        ]
        return "已更新 todos：\n" + ("\n".join(summary) if summary else "(空)")


class TodoReadTool(Tool):
    """读取当前会话的 todo 列表。"""

    def __init__(self, db_manager):
        self._db = db_manager

    name = "todo_read"
    description = "读取当前会话的 todo 列表。若刚做过 todo_write 一般不用再读，除非需要基于最新状态推理。"
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    async def execute(self, _ctx: ToolContext | None = None) -> str:
        if _ctx is None or not _ctx.session_id:
            return "[错误] 未拿到 session_id"
        meta = await self._db.get_session_metadata(_ctx.session_id)
        todos = meta.get("todos") or []
        if not todos:
            return "(尚未创建任何 todo)"
        return json.dumps(todos, ensure_ascii=False, indent=2)
