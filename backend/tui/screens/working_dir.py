"""WorkingDirPickerModal：Ctrl-W 呼出的工作目录选择器。

- 输入路径或从最近使用列表选
- 空 = 回到默认 workspace
- 最近路径存本地 ~/.mengdie/tui_recent_cwds.json
"""
from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static


_RECENT_FILE = Path.home() / ".mengdie" / "tui_recent_cwds.json"
_MAX_RECENT = 8


def _load_recent() -> list[str]:
    try:
        return json.loads(_RECENT_FILE.read_text("utf-8"))
    except Exception:
        return []


def _save_recent(items: list[str]) -> None:
    try:
        _RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _RECENT_FILE.write_text(json.dumps(items[:_MAX_RECENT], ensure_ascii=False),
                                encoding="utf-8")
    except Exception:
        pass


class WorkingDirPickerModal(ModalScreen[str | None]):
    """
    dismiss(path) 返回选中的路径（可能为空字符串 = 回到 workspace）；
    dismiss(None) 表示取消（不改变原值）。
    """

    DEFAULT_CSS = """
    WorkingDirPickerModal {
        align: center middle;
    }
    #wd-box {
        width: 80%;
        max-width: 90;
        height: 60%;
        max-height: 26;
        background: $panel;
        border: heavy $accent;
        padding: 1 2;
    }
    #wd-title { color: $accent; text-style: bold; margin-bottom: 1; }
    #wd-input { margin-bottom: 1; }
    #wd-hint { color: $text-muted; margin-bottom: 1; }
    #wd-recent { height: 1fr; background: transparent; }
    #wd-recent > ListItem { padding: 0 1; background: transparent; }
    #wd-recent > ListItem.--highlight { background: $accent 20%; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("enter",  "confirm", show=False, priority=True),
        Binding("down",   "cursor_down", show=False),
        Binding("up",     "cursor_up", show=False),
    ]

    def __init__(self, current: str = ""):
        super().__init__()
        self._current = current
        self._recent = _load_recent()

    def compose(self) -> ComposeResult:
        with Vertical(id="wd-box"):
            yield Static("🗂  工作目录", id="wd-title")
            yield Static(
                f"[dim]当前：[/dim] [cyan]{self._current or '(默认 workspace)'}[/cyan]",
                id="wd-hint", markup=True,
            )
            yield Input(placeholder="输入绝对路径（回车确认，空字符串回到 workspace）",
                        value=self._current, id="wd-input")
            yield Static("[dim]最近使用：[/dim]", markup=True)
            yield ListView(id="wd-recent")

    def on_mount(self) -> None:
        self.query_one("#wd-input", Input).focus()
        lst = self.query_one("#wd-recent", ListView)
        for r in self._recent:
            safe = str(r).replace("[", r"\[")
            item = ListItem(Static(f"📁 {safe}", markup=True))
            item.wd_path = r  # type: ignore[attr-defined]
            lst.append(item)

    def action_cursor_down(self) -> None:
        lst = self.query_one("#wd-recent", ListView)
        if lst.children:
            lst.action_cursor_down()

    def action_cursor_up(self) -> None:
        lst = self.query_one("#wd-recent", ListView)
        if lst.children:
            lst.action_cursor_up()

    def action_confirm(self) -> None:
        # 如果焦点在 ListView 且高亮到某一项 —— 用那一项
        lst = self.query_one("#wd-recent", ListView)
        try:
            if lst.has_focus and lst.index is not None and 0 <= lst.index < len(lst.children):
                item = lst.children[lst.index]
                path = getattr(item, "wd_path", None)
                if path is not None:
                    self._commit(str(path))
                    return
        except Exception:
            pass

        # 否则用输入框值
        value = self.query_one("#wd-input", Input).value.strip()
        self._commit(value)

    def _commit(self, value: str) -> None:
        # 非空 → 记录到最近使用
        if value:
            self._recent = [value] + [r for r in self._recent if r != value]
            _save_recent(self._recent)
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        item = evt.item
        path = getattr(item, "wd_path", None)
        if path is not None:
            self._commit(str(path))
