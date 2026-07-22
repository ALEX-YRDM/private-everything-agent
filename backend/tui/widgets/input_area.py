"""底部输入框。

- Enter 发送；Alt+Enter / Shift+Enter / Ctrl+J 换行
- 输入 @ 触发文件选择器（弹 modal，父级处理）
- 输入 / 且在行首 → 显示斜杠命令补全
- Ctrl+C 中断由父级捕获
"""
from __future__ import annotations

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea

from .slash_popup import SlashPopup


class MessageSubmitted(Message):
    def __init__(self, content: str):
        super().__init__()
        self.content = content


class AtTriggered(Message):
    """输入区检测到孤立的 @ 键（前面是空白或行首）→ 弹文件选择器。"""

    def __init__(self, initial_query: str = ""):
        super().__init__()
        self.initial_query = initial_query


class PasteTextRequested(Message):
    """粘贴的内容 —— 交给父级判断是不是"多路径"，走批量附件。"""

    def __init__(self, raw: str) -> None:
        super().__init__()
        self.raw = raw


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
        Binding("ctrl+j", "newline", "换行", show=False),
    ]

    def __init__(self):
        super().__init__(id="input-area")
        self.show_line_numbers = False
        self.soft_wrap = True
        # 由父级注入的 popup 引用，避免耦合布局
        self._slash_popup: SlashPopup | None = None

    def bind_slash_popup(self, popup: SlashPopup) -> None:
        self._slash_popup = popup

    # ── 事件 ────────────────────────────────────────

    def action_submit(self) -> None:
        # 若斜杠 popup 开着 → Enter 视为"选择当前项"
        if self._slash_popup and self._slash_popup.is_open:
            tpl = self._slash_popup.choose()
            self._slash_popup.close()
            if tpl is not None:
                self.text = tpl
                # 光标移到末尾
                self.cursor_location = self.document.end
            return

        content = self.text.strip()
        if not content:
            return
        self.post_message(MessageSubmitted(content))
        self.text = ""

    def action_newline(self) -> None:
        self.insert("\n")

    async def on_key(self, event: events.Key) -> None:
        popup = self._slash_popup

        # popup 打开时优先处理导航
        if popup and popup.is_open:
            if event.key in ("up",):
                event.stop(); event.prevent_default()
                popup.move_up()
                return
            if event.key in ("down",):
                event.stop(); event.prevent_default()
                popup.move_down()
                return
            if event.key == "tab":
                event.stop(); event.prevent_default()
                tpl = popup.choose()
                popup.close()
                if tpl is not None:
                    self.text = tpl
                    self.cursor_location = self.document.end
                return
            if event.key == "escape":
                event.stop(); event.prevent_default()
                popup.close()
                return

        # @ 触发文件选择器
        if event.character == "@":
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

    async def on_text_area_changed(self, evt: TextArea.Changed) -> None:
        """文本变了 → 判定是否要开/关斜杠 popup。"""
        popup = self._slash_popup
        if popup is None:
            return
        text = self.text
        # 只有整段文本以 / 开头（不含空格前）且不含换行时才补全
        stripped_head = text.lstrip()
        if text.startswith("/") and "\n" not in text:
            popup.update_query(text)
            popup.open()
        elif stripped_head.startswith("/") and text.strip() == stripped_head and "\n" not in text:
            popup.update_query(stripped_head)
            popup.open()
        else:
            popup.close()

    async def on_paste(self, event: events.Paste) -> None:
        """粘贴时把原文交给父级判定是否为多文件路径。"""
        text = event.text or ""
        # 简易启发：包含换行或者以 / 开头的路径片段 → 让父级处理
        looks_like_paths = ("\n" in text) or text.strip().startswith("/") or "\t" in text
        if looks_like_paths and len(text) < 4096:
            event.stop()
            event.prevent_default()
            self.post_message(PasteTextRequested(text))
            return
        # 否则交给 TextArea 默认粘贴行为

    def insert_path(self, path: str) -> None:
        """由父级在 FilePickerModal 返回后调用，在光标处插入 `@path `。"""
        self.insert(f"@{path} ")