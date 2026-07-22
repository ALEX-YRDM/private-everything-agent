"""ToolConfirmModal：破坏性工具执行前的确认弹窗。

对齐 web UI 的四种选项：
- allow
- deny
- trust_path（信任此目录，会话内后续同目录写入不再弹）
- trust_command（信任此命令前缀，同前缀 exec 不再弹）
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


ConfirmResult = tuple[str, str | None]   # (decision, extra)


class ToolConfirmModal(ModalScreen[ConfirmResult]):
    """
    payload：从 backend WS 收到的 tool_confirm 事件，包含：
    - id, name, args, cwd, why
    - preview 可选：{kind, ...}
    - suggested_trust_path / suggested_trust_command
    """

    DEFAULT_CSS = """
    ToolConfirmModal {
        align: center middle;
    }
    #confirm-box {
        width: 82%;
        max-width: 110;
        height: auto;
        max-height: 80%;
        background: $panel;
        border: heavy $warning;
        padding: 1 2;
    }
    #confirm-title {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }
    #confirm-content {
        height: auto;
        max-height: 24;
    }
    #confirm-buttons {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    #confirm-buttons Button {
        margin: 0 1;
        min-width: 12;
    }
    Button.-primary { background: $success; }
    Button.-danger  { background: $error; }
    Button.-trust   { background: $secondary; }
    """

    BINDINGS = [
        Binding("a", "decide('allow')",          "允许",     show=False),
        Binding("d", "decide('deny')",           "拒绝",     show=False),
        Binding("p", "decide('trust_path')",     "信任目录", show=False),
        Binding("c", "decide('trust_command')",  "信任命令", show=False),
        Binding("escape", "decide('deny')",      "拒绝",     show=False),
        Binding("enter",  "decide('allow')",     "允许",     show=False),
    ]

    def __init__(self, payload: dict[str, Any]):
        super().__init__()
        self.payload = payload

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static(
                f"⚠  工具确认  {self.payload.get('name', '?')}",
                id="confirm-title",
            )
            with VerticalScroll(id="confirm-content"):
                yield Static(self._render_content())
            with Horizontal(id="confirm-buttons"):
                yield Button("允许 (a)",       id="btn-allow", classes="-primary")
                yield Button("拒绝 (d)",       id="btn-deny",  classes="-danger")
                if self.payload.get("suggested_trust_path"):
                    yield Button("信任目录 (p)",   id="btn-trust-path", classes="-trust")
                if self.payload.get("suggested_trust_command"):
                    yield Button("信任命令 (c)",   id="btn-trust-cmd",  classes="-trust")

    def _render_content(self) -> Any:
        from rich.console import Group

        parts: list[Any] = []

        # why 说明
        why = self.payload.get("why") or ""
        if why:
            parts.append(Text(why, style="dim"))
            parts.append(Text(""))  # 空行

        # cwd
        cwd = self.payload.get("cwd")
        if cwd:
            parts.append(Text.assemble(("cwd: ", "dim"), (str(cwd), "cyan")))
            parts.append(Text(""))

        # 参数
        args = self.payload.get("args") or {}
        try:
            args_pretty = json.dumps(args, ensure_ascii=False, indent=2)
        except Exception:
            args_pretty = str(args)
        parts.append(Text("参数：", style="bold"))
        parts.append(Syntax(args_pretty, "json", theme="ansi_dark",
                            background_color="default", word_wrap=True,
                            line_numbers=False))

        # preview（可选）
        preview = self.payload.get("preview")
        if preview:
            kind = preview.get("kind")
            if kind == "patch":
                parts.append(Text("\ndiff 预览：", style="bold"))
                parts.append(Syntax(preview.get("patch", ""), "diff",
                                    theme="ansi_dark", background_color="default",
                                    word_wrap=True))
            elif kind == "exec":
                parts.append(Text("\n命令：", style="bold"))
                parts.append(Text(preview.get("command", ""), style="yellow"))
            elif kind == "file":
                parts.append(Text.assemble(
                    ("\n目标：", "bold"),
                    (str(preview.get("path", "")), "cyan"),
                ))

        return Group(*parts)

    # ── 事件 ──────────────────────────────────────

    def on_button_pressed(self, evt: Button.Pressed) -> None:
        mapping = {
            "btn-allow":       ("allow", None),
            "btn-deny":        ("deny", None),
            "btn-trust-path":  ("trust_path", self.payload.get("suggested_trust_path")),
            "btn-trust-cmd":   ("trust_command", self.payload.get("suggested_trust_command")),
        }
        if evt.button.id in mapping:
            self.dismiss(mapping[evt.button.id])

    def action_decide(self, decision: str) -> None:
        extra_map = {
            "trust_path":    self.payload.get("suggested_trust_path"),
            "trust_command": self.payload.get("suggested_trust_command"),
        }
        extra = extra_map.get(decision)
        # trust_path / trust_command 没有 suggested 值时退化成 allow
        if decision in ("trust_path", "trust_command") and not extra:
            decision = "allow"
        self.dismiss((decision, extra))
