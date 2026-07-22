"""MCPPane：MCP server 列表 + 状态（F6）。

- ListView 承载条目
- Enter：reconnect
- t：toggle enable
"""
from __future__ import annotations

from typing import Any

from textual.binding import Binding
from textual.message import Message
from textual.widgets import ListItem, ListView, Static


class MCPReconnectRequested(Message):
    def __init__(self, server_id: int):
        super().__init__()
        self.server_id = server_id


class MCPToggleRequested(Message):
    def __init__(self, server_id: int):
        super().__init__()
        self.server_id = server_id


_STATUS_STYLE = {
    "connected":    ("green",  "●"),
    "disconnected": ("dim",    "○"),
    "error":        ("red",    "!"),
}


class _MCPItem(ListItem):
    def __init__(self, server: dict[str, Any]):
        self.server_id = server.get("id") or 0
        self.server_name = server.get("name", "?")
        status = str(server.get("status", "?")).lower()
        color, icon = _STATUS_STYLE.get(status, ("yellow", "?"))
        enabled = bool(server.get("enabled", True))
        tools_count = server.get("tools_count", 0)
        err = server.get("error_msg") or server.get("error") or ""

        name_safe = str(self.server_name).replace("[", r"\[")
        enable_tag = "" if enabled else " [dim](disabled)[/dim]"
        line1 = f"[{color}]{icon}[/{color}] [bold]{name_safe}[/bold]{enable_tag}"
        line2 = f"  [dim]status:[/dim] {status}  [dim]tools:[/dim] {tools_count}"
        if err:
            err_safe = str(err)[:80].replace("[", r"\[")
            line2 += f"\n  [red dim]{err_safe}[/red dim]"

        super().__init__(Static(f"{line1}\n{line2}", markup=True))


class MCPPane(ListView):
    DEFAULT_CSS = """
    MCPPane {
        height: 1fr;
        padding: 0;
        background: transparent;
    }
    MCPPane > ListItem {
        background: transparent;
        padding: 0 1;
    }
    MCPPane > ListItem.--highlight {
        background: $accent 20%;
    }
    """

    BINDINGS = [
        Binding("t", "toggle", "toggle", show=False),
    ]

    def __init__(self):
        super().__init__(id="mcp-pane")
        self._servers: list[dict[str, Any]] = []

    def set_servers(self, servers: list[dict[str, Any]]) -> None:
        self._servers = servers or []
        self.clear()
        for s in self._servers:
            self.append(_MCPItem(s))

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        item = evt.item
        if isinstance(item, _MCPItem):
            self.post_message(MCPReconnectRequested(item.server_id))

    def action_toggle(self) -> None:
        idx = self.index
        if idx is None or idx < 0 or idx >= len(self.children):
            return
        item = self.children[idx]
        if isinstance(item, _MCPItem):
            self.post_message(MCPToggleRequested(item.server_id))
