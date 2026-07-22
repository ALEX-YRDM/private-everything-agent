"""FilePickerModal：@ 触发的文件路径快速选择器。

- 输入框实时搜文件（走 /api/sessions/{id}/files/search）
- 上下方向键选、Enter 插入
- Esc 取消
"""
from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static


class FilePickerModal(ModalScreen[str | None]):
    """dismiss(path) 返回选中的路径；dismiss(None) 表示取消。"""

    DEFAULT_CSS = """
    FilePickerModal {
        align: center middle;
    }
    #picker-box {
        width: 70%;
        max-width: 80;
        height: 60%;
        max-height: 24;
        background: $panel;
        border: heavy $accent;
        padding: 1 1;
    }
    #picker-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    #picker-input {
        margin-bottom: 1;
    }
    #picker-results {
        height: 1fr;
        background: transparent;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("enter",  "confirm", show=False, priority=True),
        Binding("down",   "cursor_down", show=False),
        Binding("up",     "cursor_up", show=False),
    ]

    def __init__(self, client, session_id: str, initial_query: str = ""):
        super().__init__()
        self._client = client
        self._session_id = session_id
        self._initial_query = initial_query
        self._search_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Static("插入文件路径  [dim](Enter 选中 · Esc 取消)[/dim]",
                         id="picker-title")
            yield Input(placeholder="输入文件名关键字…",
                        value=self._initial_query, id="picker-input")
            yield ListView(id="picker-results")

    def on_mount(self) -> None:
        self.query_one("#picker-input", Input).focus()
        if self._initial_query:
            asyncio.create_task(self._search(self._initial_query))

    async def on_input_changed(self, evt: Input.Changed) -> None:
        # 简单防抖
        if self._search_task and not self._search_task.done():
            self._search_task.cancel()
        q = evt.value.strip()
        if not q:
            self.query_one("#picker-results", ListView).clear()
            return
        self._search_task = asyncio.create_task(self._search(q))

    async def _search(self, q: str) -> None:
        await asyncio.sleep(0.15)  # 简单防抖
        try:
            results = await self._client.search_files(self._session_id, q, limit=20)
        except Exception:
            results = []
        lst = self.query_one("#picker-results", ListView)
        lst.clear()
        for r in results:
            path = r.get("path") or ""
            safe = path.replace("[", r"\[")
            item = ListItem(Static(safe, markup=True))
            # 把路径存到 item 上，避免选中后要从 Static renderable 反解
            item.session_path = path  # type: ignore[attr-defined]
            lst.append(item)
        if lst.children:
            lst.index = 0

    def action_cursor_down(self) -> None:
        lst = self.query_one("#picker-results", ListView)
        if lst.children:
            lst.action_cursor_down()

    def action_cursor_up(self) -> None:
        lst = self.query_one("#picker-results", ListView)
        if lst.children:
            lst.action_cursor_up()

    def action_confirm(self) -> None:
        lst = self.query_one("#picker-results", ListView)
        idx = lst.index
        if idx is None or idx < 0 or idx >= len(lst.children):
            self.dismiss(None)
            return
        item = lst.children[idx]
        # 优先用我们自己塞在 item.session_path 上的原始字符串
        path = getattr(item, "session_path", None)
        if not path:
            self.dismiss(None)
            return
        self.dismiss(str(path))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        # 鼠标点选也走 confirm
        self.action_confirm()
