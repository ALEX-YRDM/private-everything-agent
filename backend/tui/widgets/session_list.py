"""SessionList：左侧会话列表 widget。

- 支持方向键选择 / Enter 打开 / d 删除 / r 重命名
- 高亮当前会话
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import ListItem, ListView, Static


class SessionSelected(Message):
    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id


class SessionDeleteRequested(Message):
    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id


class SessionRenameRequested(Message):
    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id


def _humanize(iso_ts: str | None) -> str:
    if not iso_ts:
        return ""
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return iso_ts[:16]
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = (now - dt).total_seconds()
    if diff < 60:
        return "刚刚"
    if diff < 3600:
        return f"{int(diff // 60)}m"
    if diff < 86400:
        return f"{int(diff // 3600)}h"
    if diff < 86400 * 30:
        return f"{int(diff // 86400)}d"
    return dt.strftime("%m-%d")


class SessionListItem(ListItem):
    def __init__(self, session: dict):
        title = (session.get("title") or "新会话").strip() or "新会话"
        ts = _humanize(session.get("updated_at") or session.get("created_at"))
        # 用 Static + markup 承载显示，避开 Label 在 selection 上的兼容坑
        safe_title = title[:24].replace("[", r"\[")
        content = Static(f"[dim]{ts:>4}[/dim]  {safe_title}", markup=True)
        super().__init__(content)
        self.session_id = session["id"]
        self.session_title = title


class SessionList(ListView):
    """会话列表。"""

    BINDINGS = [
        Binding("d", "delete", "删除", show=False),
        Binding("r", "rename", "重命名", show=False),
    ]

    def __init__(self):
        super().__init__(id="session-list")

    def load_sessions(self, sessions: list[dict], active_id: str | None) -> None:
        """全量刷新列表；active_id 会被自动高亮。"""
        # 记住当前列表长度，逐个 remove_children 避免重建整个 widget
        self.clear()
        for s in sessions:
            self.append(SessionListItem(s))
        # 高亮当前会话
        if active_id:
            for idx, child in enumerate(self.children):
                if isinstance(child, SessionListItem) and child.session_id == active_id:
                    self.index = idx
                    break

    def get_current(self) -> SessionListItem | None:
        idx = self.index
        if idx is None or idx < 0 or idx >= len(self.children):
            return None
        child = self.children[idx]
        return child if isinstance(child, SessionListItem) else None

    # ── 事件 ───────────────────────────────────────

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        item = evt.item
        if isinstance(item, SessionListItem):
            self.post_message(SessionSelected(item.session_id))

    def action_delete(self) -> None:
        item = self.get_current()
        if item is not None:
            self.post_message(SessionDeleteRequested(item.session_id))

    def action_rename(self) -> None:
        item = self.get_current()
        if item is not None:
            self.post_message(SessionRenameRequested(item.session_id))
