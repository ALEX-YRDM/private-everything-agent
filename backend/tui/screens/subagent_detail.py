"""SubAgentDetailModal：查看某个 subagent 的完整会话记录。"""
from __future__ import annotations

from rich.markdown import Markdown
from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import RichLog, Static

from ..widgets.chat_view import _split_think


class SubAgentDetailModal(ModalScreen[None]):
    """展示 subagent 完整消息流（只读）。"""

    DEFAULT_CSS = """
    SubAgentDetailModal {
        align: center middle;
    }
    #sad-box {
        width: 90%;
        max-width: 120;
        height: 90%;
        max-height: 46;
        background: $panel;
        border: heavy $accent;
        padding: 1 2;
    }
    #sad-title { color: $accent; text-style: bold; margin-bottom: 1; }
    #sad-body {
        height: 1fr;
        background: transparent;
    }
    """

    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("q",      "close", show=False),
    ]

    def __init__(self, task: str, messages: list[dict]):
        super().__init__()
        self._task = task
        self._messages = messages or []

    def compose(self) -> ComposeResult:
        with Vertical(id="sad-box"):
            yield Static(f"▸ [b]子任务[/b]  [dim]{self._task[:80]}[/dim]",
                         id="sad-title", markup=True)
            yield RichLog(markup=True, wrap=True, id="sad-body")

    def on_mount(self) -> None:
        log = self.query_one("#sad-body", RichLog)
        import json
        for m in self._messages:
            role = m.get("role") or ""
            content = m.get("content") or ""
            if role == "user":
                log.write(f"[cyan bold]▎ 任务[/cyan bold]")
                log.write(content.replace("[", r"\["))
                log.write("")
            elif role == "assistant":
                # 拆 think
                think, body = _split_think(content)
                log.write(f"[green bold]▎ 输出[/green bold]")
                if think:
                    preview = think.split("\n", 1)[0][:120].replace("[", r"\[")
                    log.write(f"[magenta dim italic]▸ think: {preview}…[/magenta dim italic]")
                if body:
                    try:
                        log.write(Markdown(body, code_theme="monokai"))
                    except Exception:
                        log.write(body.replace("[", r"\["))
                # tool_calls
                tcs_raw = m.get("tool_calls")
                if tcs_raw:
                    try:
                        tcs = json.loads(tcs_raw) if isinstance(tcs_raw, str) else tcs_raw
                    except Exception:
                        tcs = []
                    for tc in tcs or []:
                        fn = tc.get("function") or {}
                        name = fn.get("name") or tc.get("name") or "?"
                        args = fn.get("arguments") or "{}"
                        log.write(f"[yellow]▶ {name}[/yellow]")
                        try:
                            log.write(Syntax(args, "json", theme="ansi_dark",
                                             background_color="default"))
                        except Exception:
                            pass
                log.write("")
            elif role == "tool":
                log.write(f"[dim]▎ 工具结果 ({m.get('name','?')})[/dim]")
                content_preview = content
                if len(content_preview) > 2000:
                    content_preview = content_preview[:2000] + "\n…[截断]"
                log.write(content_preview.replace("[", r"\["))
                log.write("")

    def action_close(self) -> None:
        self.dismiss(None)
