"""SettingsScreen：Ctrl-K 呼出的设置屏。

- 切模型（全局 or 本会话）
- 只读展示 max_tokens / temperature / context_window / workspace
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, RadioButton, RadioSet, Static


class SettingsScreen(ModalScreen):
    """模型切换 + 只读配置。

    dismiss 返回 dict：{scope: "global"|"session", model: str | None}
    None 表示取消。
    """

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-box {
        width: 76%;
        max-width: 100;
        height: 78%;
        max-height: 36;
        background: $panel;
        border: heavy $accent;
        padding: 1 2;
    }
    #settings-title { color: $accent; text-style: bold; margin-bottom: 1; }
    #settings-config {
        color: $text-muted;
        margin-bottom: 1;
    }
    #scope-row {
        height: 3;
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
        Binding("ctrl+g", "set_scope_global",  show=False),
        Binding("ctrl+l", "set_scope_session", show=False),
    ]

    def __init__(
        self,
        client,
        config: dict,
        models: list[dict],
        current_model: str,
        session_model: str | None = None,
        has_session: bool = True,
    ):
        super().__init__()
        self._client = client
        self._config = config
        self._models = models or []
        self._current = current_model
        self._session_model = session_model
        self._has_session = has_session
        # 若当前会话已有 model → 默认作用范围选"本会话"，否则"全局"
        self._scope = "session" if session_model else "global"

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-box"):
            yield Static("⚙  设置", id="settings-title")
            cfg = self._config
            sess_line = ""
            if self._has_session:
                sess_val = self._session_model or "(未设置，跟随全局)"
                sess_line = f"\n[dim]本会话模型：[/dim][magenta]{sess_val}[/magenta]"
            info = (
                f"[dim]全局模型：[/dim][cyan]{self._current}[/cyan]{sess_line}\n"
                f"[dim]max_tokens:[/dim] {cfg.get('max_tokens', '?')}  "
                f"[dim]temperature:[/dim] {cfg.get('temperature', '?')}  "
                f"[dim]context_window:[/dim] {cfg.get('context_window_tokens', '?')}\n"
                f"[dim]workspace:[/dim] {cfg.get('workspace', '?')}"
            )
            yield Static(info, id="settings-config", markup=True)

            # scope 选择
            with Horizontal(id="scope-row"):
                with RadioSet(id="scope-set"):
                    yield RadioButton("本会话",  value=(self._scope == "session"), id="scope-session")
                    yield RadioButton("全局",   value=(self._scope == "global"),  id="scope-global")

            yield Static(
                "[dim]↓/↑ 选择模型 · Enter 切换 · Ctrl-G 全局 · Ctrl-L 本会话 · Esc 关闭[/dim]",
                markup=True,
            )
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
            for i, child in enumerate(lst.children):
                if getattr(child, "model_id", None) == (
                    self._session_model or self._current
                ):
                    lst.index = i
                    break
            else:
                lst.index = 0

    def on_radio_set_changed(self, evt: RadioSet.Changed) -> None:
        idx = evt.radio_set.pressed_index
        self._scope = "session" if idx == 0 else "global"

    def action_set_scope_session(self) -> None:
        self._scope = "session"
        rs = self.query_one("#scope-set", RadioSet)
        rs.pressed_index = 0

    def action_set_scope_global(self) -> None:
        self._scope = "global"
        rs = self.query_one("#scope-set", RadioSet)
        rs.pressed_index = 1

    def action_confirm(self) -> None:
        lst = self.query_one("#model-list", ListView)
        idx = lst.index
        if idx is None or idx < 0 or idx >= len(lst.children):
            self.dismiss(None)
            return
        item = lst.children[idx]
        model_id = getattr(item, "model_id", None)
        if not model_id:
            self.dismiss(None)
            return
        self.dismiss({"scope": self._scope, "model": model_id})

    def action_close(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        self.action_confirm()
