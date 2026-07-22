"""SettingsScreen：Ctrl-, 呼出的设置屏（当前只做模型切换 + 只读配置概览）。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static


class SettingsScreen(ModalScreen):
    """当前只做模型切换 + 展示只读配置。"""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-box {
        width: 70%;
        max-width: 90;
        height: 70%;
        max-height: 32;
        background: $panel;
        border: heavy $accent;
        padding: 1 2;
    }
    #settings-title { color: $accent; text-style: bold; margin-bottom: 1; }
    #settings-config {
        color: $text-muted;
        margin-bottom: 1;
    }
    #model-list {
        height: 1fr;
        background: transparent;
    }
    #model-list > ListItem {
        background: transparent;
        padding: 0 1;
    }
    #model-list > ListItem.--highlight {
        background: $accent 20%;
    }
    """

    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("q",      "close", show=False),
        Binding("enter",  "confirm", show=False, priority=True),
    ]

    def __init__(self, client, config: dict, models: list[dict], current_model: str):
        super().__init__()
        self._client = client
        self._config = config
        self._models = models or []
        self._current = current_model

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-box"):
            yield Static("⚙  设置", id="settings-title")
            cfg = self._config
            info = (
                f"[dim]当前模型：[/dim][cyan]{self._current}[/cyan]\n"
                f"[dim]max_tokens:[/dim] {cfg.get('max_tokens', '?')}  "
                f"[dim]temperature:[/dim] {cfg.get('temperature', '?')}  "
                f"[dim]context_window:[/dim] {cfg.get('context_window_tokens', '?')}\n"
                f"[dim]workspace:[/dim] {cfg.get('workspace', '?')}"
            )
            yield Static(info, id="settings-config", markup=True)
            yield Static("[dim]↓/↑ 选择模型 · Enter 切换 · Esc 关闭[/dim]", markup=True)
            yield ListView(id="model-list")

    def on_mount(self) -> None:
        lst = self.query_one("#model-list", ListView)
        for m in self._models:
            mid = m.get("id") or m.get("model_id") or ""
            label = m.get("label") or mid
            provider = m.get("provider", "")
            marker = "[green]●[/green]" if mid == self._current else "○"
            mid_safe = mid.replace("[", r"\[")
            provider_safe = str(provider).replace("[", r"\[")
            label_safe = str(label).replace("[", r"\[")
            text = f"{marker} [bold]{label_safe}[/bold]  [dim]({provider_safe})[/dim]\n  [dim]{mid_safe}[/dim]"
            item = ListItem(Static(text, markup=True))
            item.model_id = mid  # type: ignore[attr-defined]
            lst.append(item)
        if lst.children:
            # 定位到当前模型
            for i, child in enumerate(lst.children):
                if getattr(child, "model_id", None) == self._current:
                    lst.index = i
                    break
            else:
                lst.index = 0

    def action_confirm(self) -> None:
        lst = self.query_one("#model-list", ListView)
        idx = lst.index
        if idx is None or idx < 0 or idx >= len(lst.children):
            self.dismiss(None)
            return
        item = lst.children[idx]
        model_id = getattr(item, "model_id", None)
        self.dismiss(model_id)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        self.action_confirm()
