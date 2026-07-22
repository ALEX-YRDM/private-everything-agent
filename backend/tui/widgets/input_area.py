"""底部输入框。

- Enter 发送；Alt+Enter / Shift+Enter 换行
- 输入 @ 触发文件选择器（弹 modal，父级处理）
- Ctrl+C 中断由父级捕获
"""
from __future__ import annotations

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea


class MessageSubmitted(Message):
    def __init__(self, content: str):
        super().__init__()
        self.content = content


class AtTriggered(Message):
    """输入区检测到孤立的 @ 键（前面是空白或行首）→ 弹文件选择器。"""

    def __init__(self, initial_query: str = ""):
        super().__init__()
        self.initial_query = initial_query


class InputArea(TextArea):
    DEFAULT_CSS = """
    InputArea {
        height: auto;
        min-height: 3;
        max-height: 12;
        border: solid $accent;
        padding: 0 1;
    }
    InputArea:focus {
        border: heavy $accent;
    }
    """

    BINDINGS = [
        Binding("enter", "submit", "发送", show=False, priority=True),
        Binding("shift+enter", "newline", "换行", show=False),
        Binding("alt+enter", "newline", "换行", show=False),
    ]

    def __init__(self):
        super().__init__(id="input-area")
        self.show_line_numbers = False
        self.soft_wrap = True

    def action_submit(self) -> None:
        content = self.text.strip()
        if not content:
            return
        self.post_message(MessageSubmitted(content))
        self.text = ""

    def action_newline(self) -> None:
        self.insert("\n")

    async def on_key(self, event: events.Key) -> None:
        """输入 @ 且前面是行首或空白时，拦截并发消息给父级去弹 modal。"""
        if event.character == "@":
            # 判断前面是不是空白/行首
            try:
                row, col = self.cursor_location
                line = self.document.get_line(row)
            except Exception:
                return
            prefix_ok = col == 0 or (col > 0 and line[col - 1].isspace())
            if prefix_ok:
                event.stop()
                event.prevent_default()
                self.post_message(AtTriggered(""))

    def insert_path(self, path: str) -> None:
        """由父级在 FilePickerModal 返回后调用，在光标处插入 `@path `。"""
        self.insert(f"@{path} ")