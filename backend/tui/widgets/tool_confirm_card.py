"""ToolConfirmCard：内联的破坏性工具确认卡，直接 mount 到 ChatView。

- 不弹 modal，不打断消息流
- 快捷键：a=允许 d=拒绝 p=信任目录 c=信任命令
- 键盘焦点在卡片时才响应
"""
from __future__ import annotations

import json
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import RichLog


class ConfirmDecided(Message):
    def __init__(self, tc_id: str, decision: str, extra: str | None = None):
        super().__init__()
        self.tc_id = tc_id
        self.decision = decision
        self.extra = extra


class ToolConfirmCard(RichLog):
    """
    用 RichLog 承载确认卡内容——写入即可，避免 Static 在 pane 切换 /
    动态 mount 场景下 visual=None 崩溃的问题。
    """

    DEFAULT_CSS = """
    ToolConfirmCard {
        height: auto;
        max-height: 30;
        margin: 0 1;
        border: heavy $warning;
        padding: 0 1;
        background: transparent;
    }
    ToolConfirmCard:focus {
        border: heavy $success;
    }
    """

    can_focus = True

    BINDINGS = [
        Binding("a", "decide('allow')",         "允许"),
        Binding("d", "decide('deny')",          "拒绝"),
        Binding("p", "decide('trust_path')",    "信任目录"),
        Binding("c", "decide('trust_command')", "信任命令"),
        Binding("enter", "decide('allow')",     "允许", show=False),
        Binding("escape", "decide('deny')",     "拒绝", show=False),
    ]

    def __init__(self, payload: dict[str, Any]):
        super().__init__(markup=True, wrap=True, highlight=False)
        self.payload = payload
        self.tc_id = payload.get("id") or ""
        self._decided = False

    def on_mount(self) -> None:
        self._render()
        self.focus()

    def _render(self) -> None:
        self.clear()
        payload = self.payload
        name = payload.get("name", "?")
        why = payload.get("why") or ""
        cwd = payload.get("cwd") or ""

        self.write(f"[yellow bold]⚠  工具确认  {name}[/yellow bold]")
        if why:
            self.write(f"[dim]{why}[/dim]")
        if cwd:
            self.write(f"[dim]cwd:[/dim] [cyan]{cwd}[/cyan]")
        self.write("")

        # 参数（用 rich Syntax 保证高亮）
        args = payload.get("args") or {}
        try:
            args_pretty = json.dumps(args, ensure_ascii=False, indent=2)
        except Exception:
            args_pretty = str(args)
        self.write("[bold]参数：[/bold]")
        self.write(Syntax(args_pretty, "json", theme="ansi_dark",
                          background_color="default", word_wrap=True,
                          line_numbers=False))

        # preview
        preview = payload.get("preview")
        if preview:
            kind = preview.get("kind")
            if kind == "patch":
                self.write("")
                self.write("[bold]diff：[/bold]")
                self.write(Syntax(preview.get("patch", ""), "diff",
                                  theme="ansi_dark", background_color="default",
                                  word_wrap=True))
            elif kind == "exec":
                self.write("")
                self.write(f"[bold]命令：[/bold] [yellow]{preview.get('command', '')}[/yellow]")
            elif kind == "file":
                self.write("")
                self.write(f"[bold]目标：[/bold] [cyan]{preview.get('path', '')}[/cyan]")

        # 按钮提示
        has_path = bool(payload.get("suggested_trust_path"))
        has_cmd  = bool(payload.get("suggested_trust_command"))
        hints = ["[a] 允许", "[d] 拒绝"]
        if has_path:
            hints.append("[p] 信任目录")
        if has_cmd:
            hints.append("[c] 信任命令")
        self.write("")
        self.write(f"[bold cyan]{' · '.join(hints)}[/bold cyan]")

    def action_decide(self, decision: str) -> None:
        if self._decided:
            return
        extra_map = {
            "trust_path":    self.payload.get("suggested_trust_path"),
            "trust_command": self.payload.get("suggested_trust_command"),
        }
        extra = extra_map.get(decision)
        if decision in ("trust_path", "trust_command") and not extra:
            decision = "allow"

        self._decided = True
        self.post_message(ConfirmDecided(self.tc_id, decision, extra))

        # 视觉反馈：清空后写一条完成信息
        label = {
            "allow":         "✓ 允许",
            "deny":          "✗ 拒绝",
            "trust_path":    "★ 信任目录",
            "trust_command": "★ 信任命令",
        }.get(decision, decision)
        color = "green" if decision != "deny" else "red"
        self.clear()
        self.write(f"[{color} bold]{label}[/{color} bold]  [dim]{self.payload.get('name', '')}[/dim]")

        # 焦点让出
        try:
            self.app.set_focus(None)
        except Exception:
            pass
