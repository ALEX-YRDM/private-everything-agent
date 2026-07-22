"""SlashPopup：输入框里输入 `/xxx` 时弹一层候选。

- 键盘：↑/↓ 移动、Tab/Enter 选中、Esc 关闭
- 父级 InputArea 负责判定该显示还是隐藏，并把选中的命令写回 InputArea
"""
from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static


@dataclass
class SlashCommand:
    name: str          # 含前导 "/"，如 "/rename"
    template: str      # 补全后插入到 InputArea 的完整文本，如 "/rename "
    desc: str          # 一行说明


# 所有可用的 / 命令（新增命令时改这里）
COMMANDS: list[SlashCommand] = [
    SlashCommand("/rename",      "/rename ",         "重命名当前会话"),
    SlashCommand("/delete",      "/delete",          "删除当前会话（需 /delete confirm 确认）"),
    SlashCommand("/paste-img",   "/paste-img ",      "追加剪贴板图片到附件区"),
    SlashCommand("/paste",       "/paste",           "追加剪贴板图片到附件区（别名）"),
    SlashCommand("/attach",      "/attach ",         "追加本地文件到附件区（支持 glob）"),
    SlashCommand("/attach-clear","/attach-clear",    "清空附件区"),
    SlashCommand("/copy",        "/copy last",       "复制最新 assistant 消息到剪贴板"),
    SlashCommand("/export",      "/export md",       "导出当前会话为 markdown"),
    SlashCommand("/cwd",         "/cwd ",            "设置当前会话工作目录"),
    SlashCommand("/model",       "/model ",          "为本会话切换模型"),
    SlashCommand("/trusts",      "/trusts",          "查看当前会话已信任的目录/命令"),
    SlashCommand("/allow",       "/allow ",          "允许某个待确认工具（/allow <id>）"),
    SlashCommand("/deny",        "/deny ",           "拒绝某个待确认工具（/deny <id>）"),
]


class SlashCommandChosen(Message):
    def __init__(self, template: str) -> None:
        super().__init__()
        self.template = template


class SlashPopup(Widget):
    """悬浮在 InputArea 上方的斜杠命令候选。"""

    DEFAULT_CSS = """
    SlashPopup {
        dock: bottom;
        offset-y: -12;   /* 悬浮在输入框正上方 */
        height: auto;
        max-height: 8;
        width: 60%;
        max-width: 60;
        margin: 0 1;
        background: $panel;
        border: solid $accent 70%;
        display: none;
    }
    SlashPopup.-open {
        display: block;
    }
    SlashPopup ListView {
        height: auto;
        max-height: 8;
        background: transparent;
    }
    SlashPopup ListItem {
        padding: 0 1;
        background: transparent;
    }
    SlashPopup ListItem.--highlight {
        background: $accent 20%;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._items: list[SlashCommand] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield ListView(id="slash-list")

    # ── 对外 API ────────────────────────────────────

    def update_query(self, query: str) -> None:
        """query 形如 "" / "/" / "/re" —— 过滤候选。"""
        q = (query or "").lower()
        self._items = [
            c for c in COMMANDS
            if not q or q in c.name.lower() or q in c.desc.lower()
        ]
        lst = self.query_one("#slash-list", ListView)
        lst.clear()
        for c in self._items:
            text = f"[bold cyan]{c.name}[/bold cyan]  [dim]{c.desc}[/dim]"
            lst.append(ListItem(Static(text, markup=True)))
        if lst.children:
            lst.index = 0

    def open(self) -> None:
        if not self._items:
            return
        self.add_class("-open")

    def close(self) -> None:
        self.remove_class("-open")

    @property
    def is_open(self) -> bool:
        return self.has_class("-open")

    def move_up(self) -> None:
        lst = self.query_one("#slash-list", ListView)
        if lst.children:
            lst.action_cursor_up()

    def move_down(self) -> None:
        lst = self.query_one("#slash-list", ListView)
        if lst.children:
            lst.action_cursor_down()

    def choose(self) -> str | None:
        """把当前高亮项对应的 template 返回。"""
        lst = self.query_one("#slash-list", ListView)
        idx = lst.index
        if idx is None or idx < 0 or idx >= len(self._items):
            return None
        return self._items[idx].template
