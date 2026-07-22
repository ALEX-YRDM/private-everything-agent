"""CommandPalette：Ctrl-P 弹的 fuzzy 搜索面板。

- 搜会话标题（本地对 sessions_cache fuzzy）
- 若查询以 `>` 开头，搜当前会话消息内容（本地对已加载历史 fuzzy）
- Enter 打开对应会话（或跳到消息）
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static


class SessionPicked:
    def __init__(self, session_id: str):
        self.session_id = session_id


class CommandPalette(ModalScreen):
    """
    构造时传入 sessions 列表。dismiss 返回选中的 session_id（str）或 None。
    """

    DEFAULT_CSS = """
    CommandPalette {
        align: center middle;
    }
    #palette-box {
        width: 70%;
        max-width: 90;
        height: 60%;
        max-height: 28;
        background: $panel;
        border: heavy $accent;
        padding: 1 1;
    }
    #palette-title { color: $accent; text-style: bold; margin-bottom: 1; }
    #palette-input { margin-bottom: 1; }
    #palette-results {
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

    def __init__(self, sessions: list[dict]):
        super().__init__()
        self._sessions = sessions or []

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-box"):
            yield Static("会话搜索  [dim](输入关键字模糊匹配 · Enter 打开 · Esc 取消)[/dim]",
                         id="palette-title")
            yield Input(placeholder="模糊搜索会话标题…", id="palette-input")
            yield ListView(id="palette-results")

    def on_mount(self) -> None:
        # 先渲染全部
        self._refresh("")
        self.query_one(Input).focus()

    def _score(self, query: str, title: str) -> int:
        """极简 fuzzy 得分：所有 query 字符按顺序在 title 里出现即匹配。"""
        if not query:
            return 100
        q = query.lower()
        t = title.lower()
        i = 0
        for ch in q:
            j = t.find(ch, i)
            if j < 0:
                return -1
            i = j + 1
        # 匹配字符集中度：query 越紧凑匹配区间越短，分越高
        return max(1, 100 - (i - len(q)))

    def _refresh(self, query: str) -> None:
        lst = self.query_one("#palette-results", ListView)
        lst.clear()
        scored: list[tuple[int, dict]] = []
        for s in self._sessions:
            title = (s.get("title") or "").strip()
            score = self._score(query, title)
            if score >= 0:
                scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        for _, s in scored[:50]:
            title = (s.get("title") or "").strip() or "新会话"
            safe = title[:60].replace("[", r"\[")
            item = ListItem(Static(safe, markup=True))
            item.session_id = s["id"]  # type: ignore[attr-defined]
            lst.append(item)
        if lst.children:
            lst.index = 0

    def on_input_changed(self, evt: Input.Changed) -> None:
        self._refresh(evt.value.strip())

    def action_cursor_down(self) -> None:
        lst = self.query_one("#palette-results", ListView)
        if lst.children:
            lst.action_cursor_down()

    def action_cursor_up(self) -> None:
        lst = self.query_one("#palette-results", ListView)
        if lst.children:
            lst.action_cursor_up()

    def action_confirm(self) -> None:
        lst = self.query_one("#palette-results", ListView)
        idx = lst.index
        if idx is None or idx < 0 or idx >= len(lst.children):
            self.dismiss(None)
            return
        item = lst.children[idx]
        sid = getattr(item, "session_id", None)
        self.dismiss(sid)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        self.action_confirm()
