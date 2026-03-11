"""
定时任务管理工具（供 Agent 在对话中自动创建/查看/删除定时任务）。

Agent 识别到用户有"定期执行某件事"的需求时，直接调用这些工具，
无需用户手动进入设置界面操作。

cron_expr 支持两种格式：
  - 5字段 cron：  "0 8 * * *"  （分 时 日 月 周）
  - 间隔格式：    "@every 30s" / "@every 5m" / "@every 2h"
"""
from .base import Tool
from ..scheduler import validate_expr, describe_expr


class CreateTaskTool(Tool):
    name = "create_task"
    description = (
        "创建定时任务，让 Agent 按计划自动执行指定 prompt。"
        "当用户提到每天/每周/每X分钟/每隔X秒/定时/定期/提醒等周期性执行意图时，主动调用此工具。"
        "cron_expr 支持两种格式：\n"
        "  1) 5字段cron: '0 8 * * *'（每天8点）, '*/30 * * * *'（每30分钟）\n"
        "  2) 间隔格式: '@every 30s'（每30秒）, '@every 5m'（每5分钟）, '@every 2h'（每2小时）\n"
        "注意：cron 最小粒度为1分钟；需要秒级间隔必须使用 @every 格式。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "任务名称，如「每日早报」"
            },
            "cron_expr": {
                "type": "string",
                "description": (
                    "调度表达式。cron格式: '0 8 * * *'；"
                    "间隔格式: '@every 30s'/'@every 5m'/'@every 2h'"
                )
            },
            "prompt": {
                "type": "string",
                "description": "任务触发时 Agent 执行的完整指令，应尽量详细"
            },
            "model_id": {
                "type": "string",
                "description": "可选，指定执行该任务的模型，留空使用系统默认"
            },
        },
        "required": ["name", "cron_expr", "prompt"],
    }

    def __init__(self, db_manager, scheduler):
        self.db = db_manager
        self.scheduler = scheduler

    async def execute(self, name: str, cron_expr: str, prompt: str,
                      model_id: str = None) -> str:
        err = validate_expr(cron_expr)
        if err:
            return f"[错误] 调度表达式不合法：{err}"

        task = await self.db.create_task(
            name=name,
            cron_expr=cron_expr,
            prompt=prompt,
            model_id=model_id or None,
        )
        if self.scheduler:
            self.scheduler.add_task(task)

        plan_desc = describe_expr(cron_expr)
        prompt_preview = prompt[:100] + ("..." if len(prompt) > 100 else "")
        return (
            f"已创建定时任务「{name}」（ID: {task['id']}）\n"
            f"执行计划：{plan_desc}\n"
            f"执行内容：{prompt_preview}\n"
            "任务将在指定时间自动运行，结果保存到专属会话中。"
        )


class ListTasksTool(Tool):
    name = "list_tasks"
    description = "列出所有定时任务（名称、执行计划、启用状态、上次运行情况）。"
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, db_manager):
        self.db = db_manager

    async def execute(self) -> str:
        tasks = await self.db.list_tasks()
        if not tasks:
            return "当前没有任何定时任务。"
        lines = []
        for t in tasks:
            status = "启用" if t["enabled"] else "暂停"
            last = t["last_run_at"] or "从未运行"
            last_status = f"（{t['last_status']}）" if t["last_status"] else ""
            prompt_preview = t["prompt"][:60] + ("..." if len(t["prompt"]) > 60 else "")
            lines.append(
                f"#{t['id']} [{status}] {t['name']}\n"
                f"  计划：{t['cron_expr']}  |  上次运行：{last}{last_status}\n"
                f"  Prompt：{prompt_preview}"
            )
        return "\n\n".join(lines)


class DeleteTaskTool(Tool):
    name = "delete_task"
    description = "删除指定定时任务。用户说取消/停止/删除定时任务时调用。"
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "任务 ID（可先用 list_tasks 查询）"
            },
        },
        "required": ["task_id"],
    }

    def __init__(self, db_manager, scheduler):
        self.db = db_manager
        self.scheduler = scheduler

    async def execute(self, task_id: int) -> str:
        task = await self.db.get_task(task_id)
        if not task:
            return f"[错误] 未找到 ID 为 {task_id} 的定时任务"
        if self.scheduler:
            self.scheduler.remove_task(task_id)
        await self.db.delete_task(task_id)
        return f"定时任务「{task['name']}」（#{task_id}）已删除。"


class UpdateTaskTool(Tool):
    name = "update_task"
    description = (
        "修改定时任务配置：执行时间(cron_expr)、内容(prompt)、启用暂停(enabled)。"
        "用户说改成每天X点、暂停任务、恢复任务时调用。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "integer", "description": "任务 ID"},
            "cron_expr": {"type": "string", "description": "新的 cron 表达式（可选）"},
            "prompt": {"type": "string", "description": "新的执行指令（可选）"},
            "name": {"type": "string", "description": "新的任务名称（可选）"},
            "enabled": {"type": "boolean", "description": "true=启用, false=暂停（可选）"},
        },
        "required": ["task_id"],
    }

    def __init__(self, db_manager, scheduler):
        self.db = db_manager
        self.scheduler = scheduler

    async def execute(self, task_id: int, cron_expr: str = None, prompt: str = None,
                      name: str = None, enabled: bool = None) -> str:
        task = await self.db.get_task(task_id)
        if not task:
            return f"[错误] 未找到 ID 为 {task_id} 的定时任务"

        if cron_expr:
            err = validate_expr(cron_expr)
            if err:
                return f"[错误] 调度表达式不合法：{err}"

        updates: dict = {}
        if cron_expr is not None:
            updates["cron_expr"] = cron_expr
        if prompt is not None:
            updates["prompt"] = prompt
        if name is not None:
            updates["name"] = name
        if enabled is not None:
            updates["enabled"] = 1 if enabled else 0

        if not updates:
            return "[提示] 没有提供要修改的字段。"

        updated = await self.db.update_task(task_id, **updates)
        if self.scheduler:
            self.scheduler.reschedule_task(updated)

        changes = []
        if "cron_expr" in updates:
            changes.append(f"执行计划 -> {updates['cron_expr']}（{describe_expr(updates['cron_expr'])}）")
        if "name" in updates:
            changes.append(f"名称 -> {updates['name']}")
        if "prompt" in updates:
            changes.append("执行内容已更新")
        if "enabled" in updates:
            changes.append("状态 -> " + ("启用" if updates["enabled"] else "暂停"))

        return f"任务「{updated['name']}」已更新：{', '.join(changes)}"


def register_task_tools(registry, db_manager, scheduler) -> None:
    """在 AgentLoop 创建后，将任务工具注册到工具注册表。"""
    registry.register(CreateTaskTool(db_manager, scheduler))
    registry.register(ListTasksTool(db_manager))
    registry.register(DeleteTaskTool(db_manager, scheduler))
    registry.register(UpdateTaskTool(db_manager, scheduler))


def _describe_cron(expr: str) -> str:
    """兼容旧调用，委托给 scheduler.describe_expr。"""
    return describe_expr(expr)


def _describe_cron_legacy(expr: str) -> str:
    """将常见 cron 表达式转为人类可读描述（保留备用）。"""
    mapping = {
        "0 8 * * *":    "每天 08:00",
        "0 9 * * *":    "每天 09:00",
        "0 12 * * *":   "每天 12:00",
        "0 18 * * *":   "每天 18:00",
        "0 21 * * *":   "每天 21:00",
        "0 22 * * *":   "每天 22:00",
        "0 9 * * 1":    "每周一 09:00",
        "0 9 * * 5":    "每周五 09:00",
        "*/30 * * * *": "每30分钟",
        "0 * * * *":    "每小时整点",
        "0 0 * * *":    "每天午夜 00:00",
    }
    return mapping.get(expr.strip(), expr)
