"""
SpawnSubAgentsTool — 并行派发多个 SubAgent 执行独立子任务。

设计要点：
- 每个 SubAgent 在独立的 Session 中运行（完整执行记录持久化）
- 所有 SubAgent 通过 asyncio.gather 并行执行
- 执行事件通过 stream_callback 实时推送到主 Agent 的 WebSocket 流
- SubAgent 不能再派发 SubAgent（depth 限制），防止无限递归
"""

import asyncio
import json
from loguru import logger
from .base import StreamingTool


class SpawnSubAgentsTool(StreamingTool):

    def __init__(self, main_loop):
        # 持有主 AgentLoop 引用，用于创建 SubAgent 实例和访问 session_manager
        self._main_loop = main_loop

    @property
    def name(self) -> str:
        return "spawn_subagents"

    @property
    def description(self) -> str:
        return (
            "并行派发多个独立 SubAgent 执行子任务。\n\n"
            "**适用场景：**\n"
            "- 任务可分解为互相独立的子任务（并行执行更高效）\n"
            "- 需要多路信息收集后聚合（如同时搜索多个主题）\n"
            "- 不同子任务需要不同工具组合\n\n"
            "**注意：**\n"
            "- 每个 SubAgent 在独立 Session 中运行，完成后返回结果供你聚合\n"
            "- SubAgent 不加载 Skills，专注于完成具体操作\n"
            "- 子任务描述应自包含、清晰，不依赖对话上下文"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "description": "子任务列表，将并行执行",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "任务唯一标识，如 sa-1、sa-search、sa-analyze",
                            },
                            "description": {
                                "type": "string",
                                "description": "子任务的完整描述（清晰、自包含，SubAgent 只凭此执行）",
                            },
                            "tools": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "允许此 SubAgent 使用的工具名称列表（不传则使用所有可用工具，spawn_subagents 始终排除）",
                            },
                        },
                        "required": ["id", "description"],
                    },
                    "minItems": 1,
                }
            },
            "required": ["tasks"],
        }

    async def execute_streaming(
        self,
        stream_callback,
        tasks: list[dict],
    ) -> str:
        parent_session_id = getattr(self._main_loop, "_current_session_id", None)

        async def run_one(task: dict) -> dict:
            task_id = task["id"]
            task_desc = task["description"]
            allowed_tools: list[str] | None = task.get("tools") or None

            # 1. 为此 SubAgent 创建独立 Session
            session_id = await self._main_loop.sessions.create_subagent_session(
                parent_session_id=parent_session_id or "unknown",
                task_id=task_id,
                task=task_desc,
            )

            # 2. 通知前端 SubAgent 已启动
            stream_callback({
                "type": "subagent_start",
                "subagent_id": task_id,
                "session_id": session_id,
                "task": task_desc,
            })

            # 3. 创建 SubAgent 实例并运行
            sub_loop = self._main_loop.create_subagent_loop(allowed_tools=allowed_tools)
            result = ""
            try:
                async for event in sub_loop.process_stream(
                    session_id=session_id,
                    user_content=task_desc,
                ):
                    stream_callback({
                        "type": "subagent_event",
                        "subagent_id": task_id,
                        "event": event,
                    })
                    if event.get("type") == "done":
                        result = event.get("content") or ""

                stream_callback({
                    "type": "subagent_done",
                    "subagent_id": task_id,
                    "result": result,
                })
                return {
                    "id": task_id,
                    "status": "completed",
                    "session_id": session_id,
                    "result": result,
                }
            except Exception as e:
                error_msg = str(e)
                logger.exception(f"SubAgent {task_id} 执行出错: {e}")
                stream_callback({
                    "type": "subagent_done",
                    "subagent_id": task_id,
                    "result": f"[执行失败] {error_msg}",
                    "error": error_msg,
                })
                return {
                    "id": task_id,
                    "status": "failed",
                    "session_id": session_id,
                    "error": error_msg,
                }

        # 并行执行所有子任务
        raw_results = await asyncio.gather(
            *[run_one(t) for t in tasks],
            return_exceptions=True,
        )

        final_results = []
        for i, res in enumerate(raw_results):
            if isinstance(res, Exception):
                final_results.append({
                    "id": tasks[i]["id"],
                    "status": "failed",
                    "error": str(res),
                })
            else:
                final_results.append(res)

        return json.dumps({"results": final_results}, ensure_ascii=False, indent=2)
