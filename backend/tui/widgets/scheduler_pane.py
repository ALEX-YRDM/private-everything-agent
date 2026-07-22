"""SchedulerPane：F8 显示所有定时任务。

- 列出任务名 / cron 表达式 / 启用状态
- t 切换启用状态；r 立即执行；d 删除；Enter 展开预览
- 只做只读 + 简单开关；创建走 web UI
"""
from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import ListItem, ListView, Static


class SchedulerRefreshRequested(Message):
    pass


class SchedulerToggleRequested(Message):
    def __init__(self, task_id: int) -> None:
        super().__init__()
        self.task_id = task_id


class SchedulerRunNowRequested(Message):
    def __init__(self, task_id: int) -> None:
        super().__init__()
        self.task_id = task_id


class SchedulerDeleteRequested(Message):
    def __init__(self, task_id: int) -> None:
        super().__init__()
        self.task_id = task_id


class _TaskItem(ListItem):
    def __init__(self, task: dict) -> None:
        self.task = task
        tid = task.get("id")
        name = str(task.get("name") or "(无标题)").replace("[", r"\[")
        cron = str(task.get("cron_expr") or "").replace("[", r"\[")
        enabled = bool(task.get("enabled"))
        badge = "[green]✔ 启用[/green]" if enabled else "[dim]○ 禁用[/dim]"
        text = f"[bold]{name}[/bold]  {badge}\n  [cyan]{cron}[/cyan]  [dim]#{tid}[/dim]"
        super().__init__(Static(text, markup=True))
        self.task_id = int(tid) if tid is not None else -1


class SchedulerPane(ListView):
    DEFAULT_CSS = """
    SchedulerPane {
        height: 1fr;
        background: transparent;
    }
    SchedulerPane > ListItem { padding: 0 1; background: transparent; }
    SchedulerPane > ListItem.--highlight { background: $accent 20%; }
    """

    BINDINGS = [
        Binding("t", "toggle_task",   "开关", show=False),
        Binding("r", "run_task_now",  "立即执行", show=False),
        Binding("d", "delete_task",   "删除", show=False),
        Binding("f5","refresh_list",  "刷新", show=False),
    ]

    def __init__(self) -> None:
        super().__init__(id="scheduler-list")

    def set_tasks(self, tasks: list[dict]) -> None:
        self.clear()
        for t in tasks or []:
            self.append(_TaskItem(t))
        if self.children:
            self.index = 0

    def _current(self) -> _TaskItem | None:
        if self.index is None or self.index < 0 or self.index >= len(self.children):
            return None
        item = self.children[self.index]
        return item if isinstance(item, _TaskItem) else None

    def action_toggle_task(self) -> None:
        item = self._current()
        if item and item.task_id >= 0:
            self.post_message(SchedulerToggleRequested(item.task_id))

    def action_run_task_now(self) -> None:
        item = self._current()
        if item and item.task_id >= 0:
            self.post_message(SchedulerRunNowRequested(item.task_id))

    def action_delete_task(self) -> None:
        item = self._current()
        if item and item.task_id >= 0:
            self.post_message(SchedulerDeleteRequested(item.task_id))

    def action_refresh_list(self) -> None:
        self.post_message(SchedulerRefreshRequested())
