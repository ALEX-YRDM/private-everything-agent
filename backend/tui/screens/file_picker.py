"""FilePickerModal：@ 触发的文件路径快速选择器。

- 输入框实时搜文件（走 /api/sessions/{id}/files/search）
- 上下方向键选、Space 切换多选标记、Enter 提交（有标记则返回多路径）
- Esc 取消
"""
from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static


class FilePickerModal(ModalScreen[list[str] | None]):
    """
    dismiss(paths) 返回选中的路径列表（可能只有一个）；dismiss(None) 表示取消。
    - 有多选标记时：返回标记的所有路径；
    - 没有多选标记时：返回当前高亮那一项（单选场景）。
    """

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
        Binding("space",  "toggle_mark", show=False),
        Binding("down",   "cursor_down", show=False),
        Binding("up",     "cursor_up", show=False),
    ]

    def __init__(self, client, session_id: str, initial_query: str = ""):
        super().__init__()
        self._client = client
        self._session_id = session_id
        self._initial_query = initial_query
        self._search_task: asyncio.Task | None = None
        self._marked: set[str] = set()

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Static(
                "插入文件路径  [dim](Space 标记 · Enter 选中 · Esc 取消)[/dim]",
                id="picker-title",
            )
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
            marked = path in self._marked
            check = "[green][x][/green] " if marked else "[dim][ ][/dim] "
            safe = path.replace("[", r"\[")
            item = ListItem(Static(check + safe, markup=True))
            item.session_path = path  # type: ignore[attr-defined]
            lst.append(item)
        if lst.children:
            lst.index = 0

    def _rerender_current(self) -> None:
        """标记切换后只重画一行的 checkbox（把整个列表都重画一次也可以）。"""
        lst = self.query_one("#picker-results", ListView)
        for item in lst.children:
            path = getattr(item, "session_path", None)
            if path is None:
                continue
            marked = path in self._marked
            check = "[green][x][/green] " if marked else "[dim][ ][/dim] "
            safe = path.replace("[", r"\[")
            # ListItem 的第一个子是 Static
            statics = item.query(Static)
            if statics:
                statics.first().update(check + safe)

    def action_toggle_mark(self) -> None:
        lst = self.query_one("#picker-results", ListView)
        idx = lst.index
        if idx is None or idx < 0 or idx >= len(lst.children):
            return
        item = lst.children[idx]
        path = getattr(item, "session_path", None)
        if not path:
            return
        if path in self._marked:
            self._marked.discard(path)
        else:
            self._marked.add(path)
        self._rerender_current()

    def action_cursor_down(self) -> None:
        lst = self.query_one("#picker-results", ListView)
        if lst.children:
            lst.action_cursor_down()

    def action_cursor_up(self) -> None:
        lst = self.query_one("#picker-results", ListView)
        if lst.children:
            lst.action_cursor_up()

    def action_confirm(self) -> None:
        # 有多选标记 → 返回全部；否则返回当前高亮项
        if self._marked:
            self.dismiss(sorted(self._marked))
            return
        lst = self.query_one("#picker-results", ListView)
        idx = lst.index
        if idx is None or idx < 0 or idx >= len(lst.children):
            self.dismiss(None)
            return
        item = lst.children[idx]
        path = getattr(item, "session_path", None)
        if not path:
            self.dismiss(None)
            return
        self.dismiss([str(path)])

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        # 鼠标点选也走 confirm
        self.action_confirm()
