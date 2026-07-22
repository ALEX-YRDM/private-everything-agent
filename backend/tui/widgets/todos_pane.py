"""TodosPane：显示会话级 todo 列表。"""
from __future__ import annotations

from typing import Any

from textual.widgets import RichLog


STATUS_ICON = {
    "pending":     "☐",
    "in_progress": "▶",
    "completed":   "✔",
}
STATUS_STYLE = {
    "pending":     "dim",
    "in_progress": "yellow bold",
    "completed":   "green",
}


class TodosPane(RichLog):
    """
    数据源：WS 事件 todos_update（Agent 调 todo_write 时后端广播）
    + 首次进入会话时 GET /todos。
    用 RichLog 而不是 Static —— 后者在 display 切换 + 空 renderable 组合下会崩。
    """

    DEFAULT_CSS = """
    TodosPane {
        height: 1fr;
        padding: 0 1;
        background: transparent;
    }
    """

    def __init__(self):
        super().__init__(id="todos-pane", markup=True, wrap=True, highlight=False)
        self._todos: list[dict[str, Any]] = []

    def on_mount(self) -> None:
        self._render()

    def set_todos(self, todos: list[dict[str, Any]]) -> None:
        self._todos = todos or []
        self._render()

    def _render(self) -> None:
        self.clear()
        if not self._todos:
            self.write("[dim]【无 todo】[/dim]")
            return
        done = sum(1 for t in self._todos if t.get("status") == "completed")
        total = len(self._todos)
        self.write(f"[bold cyan]进度 {done}/{total}[/bold cyan]")
        self.write("")
        for t in self._todos:
            status = t.get("status", "pending")
            icon = STATUS_ICON.get(status, "?")
            style = STATUS_STYLE.get(status, "white")
            content = str(t.get("content", "")).replace("[", r"\[")
            self.write(f"[{style}]{icon} {content}[/{style}]")
