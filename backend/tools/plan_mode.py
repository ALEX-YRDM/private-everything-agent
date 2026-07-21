"""
Plan Mode 切换工具：让 Agent 在长任务开始时主动进入规划模式，
方案定好后再退出继续实际执行。

- 存储位置：session_metadata["plan_mode"] = bool（与 API 端点共用状态）
- 状态变更后通过 stream_callback 推 plan_mode_update 事件，前端 chip 实时更新
"""
from __future__ import annotations

from .base import StreamingTool
from .context import ToolContext


class EnterPlanModeTool(StreamingTool):
    def __init__(self, db_manager):
        self._db = db_manager

    @property
    def name(self) -> str:
        return "enter_plan_mode"

    @property
    def description(self) -> str:
        return (
            "进入 Plan Mode（计划模式）。之后你只能调用只读工具（read_file / list_dir / "
            "glob / grep 等）来收集信息；write_file / edit_file / multi_edit / apply_patch / "
            "exec / spawn_background 等破坏性工具会被自动拒绝。\n\n"
            "**使用时机：**\n"
            "- 用户任务涉及**多个文件的成组改动**（大型重构、迁移、批量重命名）\n"
            "- 你需要先摸清项目结构再动手\n"
            "- 用户明确说'先出方案，让我看一下'\n\n"
            "**注意：**\n"
            "- 进入 Plan Mode 后请把方案清晰写出来（要改哪些文件、每处怎么改、每个命令预期做什么）\n"
            "- 用户确认后由用户手动关闭 Plan Mode，或你判断方案已通过时调用 exit_plan_mode"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "简短说明为什么要进入 Plan Mode（一句话）",
                },
            },
        }

    async def execute_streaming(
        self, stream_callback,
        reason: str = "",
        _ctx: ToolContext | None = None,
    ) -> str:
        if _ctx is None or not _ctx.session_id:
            return "[错误] 未拿到 session_id"
        meta = await self._db.get_session_metadata(_ctx.session_id)
        if meta.get("plan_mode"):
            return "已经处于 Plan Mode，无需重复进入"
        meta["plan_mode"] = True
        await self._db.set_session_metadata(_ctx.session_id, meta)
        stream_callback({
            "type": "plan_mode_update",
            "session_id": _ctx.session_id,
            "plan_mode": True,
            "reason": reason or None,
        })
        prefix = f"（{reason}）" if reason else ""
        return f"已进入 Plan Mode{prefix}。请按顺序写出：1) 目标 2) 涉及的文件 3) 每处改动 4) 预期影响。"


class ExitPlanModeTool(StreamingTool):
    def __init__(self, db_manager):
        self._db = db_manager

    @property
    def name(self) -> str:
        return "exit_plan_mode"

    @property
    def description(self) -> str:
        return (
            "退出 Plan Mode，恢复正常执行（破坏性工具重新可用，仍会走确认卡）。"
            "**只在用户明确批准方案后调用**；如果用户还没表态，不要自作主张退出。"
        )

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute_streaming(
        self, stream_callback,
        _ctx: ToolContext | None = None,
    ) -> str:
        if _ctx is None or not _ctx.session_id:
            return "[错误] 未拿到 session_id"
        meta = await self._db.get_session_metadata(_ctx.session_id)
        if not meta.get("plan_mode"):
            return "当前未处于 Plan Mode"
        meta["plan_mode"] = False
        await self._db.set_session_metadata(_ctx.session_id, meta)
        stream_callback({
            "type": "plan_mode_update",
            "session_id": _ctx.session_id,
            "plan_mode": False,
        })
        return "已退出 Plan Mode，可以开始实际执行了。"
