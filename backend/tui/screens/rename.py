"""简单的输入型 modal：让用户输入新会话标题。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class RenameModal(ModalScreen[str | None]):
    """dismiss(new_title) 返回新标题；dismiss(None) 表示取消。"""

    DEFAULT_CSS = """
    RenameModal {
        align: center middle;
    }
    #rename-box {
        width: 60;
        height: auto;
        background: $panel;
        border: heavy $accent;
        padding: 1 2;
    }
    #rename-title { color: $accent; text-style: bold; margin-bottom: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, current_title: str = ""):
        super().__init__()
        self.current_title = current_title

    def compose(self) -> ComposeResult:
        with Vertical(id="rename-box"):
            yield Static("重命名会话  [dim](Enter 保存 · Esc 取消)[/dim]",
                         id="rename-title")
            yield Input(value=self.current_title, placeholder="新标题",
                        id="rename-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, evt: Input.Submitted) -> None:
        value = evt.value.strip()
        self.dismiss(value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
