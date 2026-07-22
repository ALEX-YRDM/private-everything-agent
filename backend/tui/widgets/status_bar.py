"""StatusBar：底部状态栏。"""
from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Static):
    """● connected · sonnet-4.7 · plan mode ON · Ctrl-? help"""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $foreground;
        padding: 0 1;
    }
    """

    connected: reactive[bool] = reactive(False)
    model: reactive[str] = reactive("")
    plan_mode: reactive[bool] = reactive(False)
    streaming: reactive[bool] = reactive(False)
    session_title: reactive[str] = reactive("")
    hint: reactive[str] = reactive("")

    def watch_connected(self, _val: bool) -> None:    self._refresh()
    def watch_model(self, _val: str) -> None:         self._refresh()
    def watch_plan_mode(self, _val: bool) -> None:    self._refresh()
    def watch_streaming(self, _val: bool) -> None:    self._refresh()
    def watch_session_title(self, _val: str) -> None: self._refresh()
    def watch_hint(self, _val: str) -> None:          self._refresh()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        conn = "[green]●[/green] connected" if self.connected else "[red]○[/red] offline"
        model = f"[cyan]{self.model or '?'}[/cyan]"
        parts: list[str] = [conn, model]
        if self.plan_mode:
            parts.append("[magenta]plan[/magenta]")
        if self.streaming:
            parts.append("[yellow]streaming…[/yellow]")
        if self.session_title:
            parts.append(f"[dim]{self.session_title[:20]}[/dim]")
        parts.append(f"[dim]{self.hint or '? 帮助 · Ctrl-N 新建 · Ctrl-C 中断 · Ctrl-Q 退出'}[/dim]")
        self.update(Text.from_markup(" · ".join(parts)))
