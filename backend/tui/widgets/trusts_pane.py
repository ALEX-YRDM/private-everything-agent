"""TrustsPane：F7 显示当前会话已信任的目录 / 命令前缀。

- 目录 + 命令合并到一个列表，前缀区分
- Delete 键删除高亮项
- 只读展示（新增走"信任此目录 / 信任此命令"确认卡）
"""
from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import ListItem, ListView, Static


class TrustsPaneRefreshRequested(Message):
    pass


class TrustDeleteRequested(Message):
    def __init__(self, kind: str, value: str) -> None:
        super().__init__()
        self.kind = kind  # "path" | "command"
        self.value = value


class _TrustItem(ListItem):
    def __init__(self, kind: str, value: str) -> None:
        icon = "🗂" if kind == "path" else "▶"
        safe = str(value).replace("[", r"\[")
        text = f"[cyan]{icon}[/cyan] {safe}"
        super().__init__(Static(text, markup=True))
        self.kind = kind
        self.value = value


class TrustsPane(ListView):
    DEFAULT_CSS = """
    TrustsPane {
        height: 1fr;
        background: transparent;
    }
    TrustsPane > ListItem { padding: 0 1; background: transparent; }
    TrustsPane > ListItem.--highlight { background: $accent 20%; }
    """

    BINDINGS = [
        Binding("delete",    "delete_current", show=False),
        Binding("backspace", "delete_current", show=False),
        Binding("r",         "refresh",        show=False),
    ]

    def __init__(self) -> None:
        super().__init__(id="trusts-list")

    def set_data(self, paths: list[str], commands: list[str]) -> None:
        self.clear()
        for p in paths or []:
            self.append(_TrustItem("path", p))
        for c in commands or []:
            self.append(_TrustItem("command", c))
        if self.children:
            self.index = 0

    def action_delete_current(self) -> None:
        if self.index is None or self.index < 0 or self.index >= len(self.children):
            return
        item = self.children[self.index]
        if not isinstance(item, _TrustItem):
            return
        self.post_message(TrustDeleteRequested(item.kind, item.value))

    def action_refresh(self) -> None:
        self.post_message(TrustsPaneRefreshRequested())
