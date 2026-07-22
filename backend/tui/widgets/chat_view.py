"""ChatView：消息流渲染 + streaming 处理。

关键设计选择：所有条目 widget 都基于 RichLog（而不是 Static）——
Textual 8.x 的 Static 在动态 mount + display 切换场景下会出现
visual=None 崩溃。RichLog 天生为 "append 内容" 设计，永远有有效 visual。
"""
from __future__ import annotations

import json
from typing import Any

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import RichLog


class _LogCard(RichLog):
    """RichLog + margin 的基类（避免每个卡都手动设 style）。"""

    DEFAULT_CSS = """
    _LogCard {
        height: auto;
        margin: 0 1;
        padding: 0 1;
        background: transparent;
        border: round $primary 40%;
    }
    MessageBubble.-user     { border: round cyan 60%; }
    MessageBubble.-assistant { border: round green 60%; }
    MessageBubble.-system    { border: round yellow 60%; }
    MessageBubble.-thinking  { border: round magenta 40%; }
    MessageBubble.-error     { border: round red 70%; }
    ToolCallCard.-running    { border: round yellow 60%; }
    ToolCallCard.-done       { border: round green 60%; }
    ToolCallCard.-denied     { border: round red 60%; }
    ToolCallCard.-error      { border: round red 60%; }
    ThinkingBlock            { border: round magenta 40%; }
    """

    def __init__(self):
        super().__init__(markup=True, wrap=True, highlight=False, auto_scroll=False)


class MessageBubble(_LogCard):
    """一条消息 = 一个 widget。"""

    ROLE_STYLE = {
        "user":      ("cyan bold",    "▎ 你"),
        "assistant": ("green bold",   "▎ 梦蝶"),
        "system":    ("yellow",       "▎ system"),
        "thinking":  ("magenta dim",  "▎ thinking"),
        "error":     ("red bold",     "▎ 错误"),
    }

    def __init__(self, role: str, content: str = ""):
        super().__init__()
        self.role = role
        self._raw = content
        # 用 CSS class 触发 border 颜色
        self.add_class(f"-{role}")
        self._refresh()

    def set_content(self, content: str) -> None:
        self._raw = content
        self._refresh()

    def append(self, delta: str) -> None:
        self._raw += delta
        self._refresh()

    def _refresh(self) -> None:
        style, label = self.ROLE_STYLE.get(self.role, ("white", f"▎ {self.role}"))
        self.clear()
        self.write(f"[{style}]{label}[/{style}]")

        text = (self._raw or "").rstrip()
        if not text:
            self.write("[dim]…[/dim]")
            return

        # user / error / system 走纯文本；assistant 走 markdown
        if self.role in ("user", "error", "system"):
            for line in text.split("\n"):
                escaped = line.replace("[", r"\[")
                if self.role == "error":
                    self.write(f"[red]{escaped}[/red]")
                elif self.role == "system":
                    self.write(f"[yellow]{escaped}[/yellow]")
                else:
                    self.write(escaped)
        else:
            try:
                self.write(Markdown(text, code_theme="monokai"))
            except Exception:
                self.write(text.replace("[", r"\["))


class ToolCallCard(_LogCard):
    """工具调用（含 pending / running / done / denied 状态）+ 结果。"""

    STATE_ICONS = {
        "pending": "…",
        "running": "▶",
        "done":    "✓",
        "denied":  "✗",
        "error":   "!",
    }
    STATE_COLOR = {
        "running": "yellow",
        "done":    "green",
        "denied":  "red",
        "error":   "red",
    }

    def __init__(self, tc_id: str, name: str, args: dict):
        super().__init__()
        self.tc_id = tc_id
        self.tool_name = name
        self.args = args or {}
        self.state = "running"
        self.result: str | None = None
        self.deny_reason: str | None = None
        self.add_class(f"-{self.state}")
        self._refresh()

    def _set_state(self, new_state: str) -> None:
        # 清旧 class，加新的，触发 CSS border 变色
        for s in ("running", "done", "denied", "error"):
            self.remove_class(f"-{s}")
        self.state = new_state
        self.add_class(f"-{new_state}")

    def mark_done(self, result: str) -> None:
        self._set_state("done")
        self.result = result
        self._refresh()

    def mark_denied(self, reason: str) -> None:
        self._set_state("denied")
        self.deny_reason = reason
        self._refresh()

    def _refresh(self) -> None:
        icon = self.STATE_ICONS.get(self.state, "?")
        color = self.STATE_COLOR.get(self.state, "white")
        self.clear()
        safe_name = str(self.tool_name).replace("[", r"\[")
        self.write(f"[{color} bold]{icon} {safe_name}[/{color} bold]")

        try:
            args_pretty = json.dumps(self.args, ensure_ascii=False, indent=2)
        except Exception:
            args_pretty = str(self.args)
        self.write(Syntax(args_pretty, "json", theme="ansi_dark",
                          background_color="default", word_wrap=True,
                          line_numbers=False))

        if self.state == "denied" and self.deny_reason:
            safe = str(self.deny_reason).replace("[", r"\[")
            self.write(f"[red dim]已拒绝：{safe}[/red dim]")
        elif self.result is not None:
            preview = self.result
            if len(preview) > 2000:
                preview = preview[:2000] + "\n…[已截断]"
            for line in preview.split("\n"):
                escaped = line.replace("[", r"\[")
                self.write(f"[dim]{escaped}[/dim]")


class ThinkingBlock(_LogCard):
    """折叠的 thinking 块，默认一行显示，展开后显示全部。"""

    def __init__(self):
        super().__init__()
        self._raw = ""
        self.expanded = False
        self._refresh()

    def append(self, delta: str) -> None:
        self._raw += delta
        self._refresh()

    def toggle(self) -> None:
        self.expanded = not self.expanded
        self._refresh()

    def _refresh(self) -> None:
        self.clear()
        if not self._raw.strip():
            self.write("[dim]▸ thinking…[/dim]")
            return
        if self.expanded:
            for line in self._raw.split("\n"):
                escaped = line.replace("[", r"\[")
                self.write(f"[magenta dim italic]{escaped}[/magenta dim italic]")
        else:
            first_line = self._raw.strip().split("\n", 1)[0]
            preview = first_line[:80].replace("[", r"\[")
            ellipsis = "…" if len(first_line) > 80 else ""
            self.write(f"[magenta dim italic]▸ thinking: {preview}{ellipsis}[/magenta dim italic]")


class ChatView(VerticalScroll):
    """整个聊天消息流 + streaming state 追踪。"""

    DEFAULT_CSS = """
    ChatView {
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._current_assistant: MessageBubble | None = None
        self._current_thinking: ThinkingBlock | None = None
        self._tool_cards: dict[str, ToolCallCard] = {}

    # ── 消息追加接口 ───────────────────────────────

    async def add_user_message(self, content: str) -> None:
        self._current_assistant = None
        self._current_thinking = None
        bubble = MessageBubble("user", content)
        await self.mount(bubble)
        self.scroll_end(animate=False)

    async def add_system_message(self, content: str) -> None:
        bubble = MessageBubble("system", content)
        await self.mount(bubble)
        self.scroll_end(animate=False)

    async def add_error_message(self, content: str) -> None:
        bubble = MessageBubble("error", content)
        await self.mount(bubble)
        self.scroll_end(animate=False)

    async def append_thinking(self, delta: str) -> None:
        if self._current_thinking is None:
            self._current_thinking = ThinkingBlock()
            await self.mount(self._current_thinking)
        self._current_thinking.append(delta)
        self.scroll_end(animate=False)

    async def append_content_delta(self, delta: str) -> None:
        if self._current_assistant is None:
            self._current_assistant = MessageBubble("assistant", "")
            await self.mount(self._current_assistant)
        self._current_assistant.append(delta)
        self.scroll_end(animate=False)

    async def add_tool_call(self, tc_id: str, name: str, args: dict) -> None:
        card = ToolCallCard(tc_id, name, args)
        self._tool_cards[tc_id] = card
        self._current_assistant = None
        await self.mount(card)
        self.scroll_end(animate=False)

    async def add_confirm_card(self, payload: dict) -> None:
        """内联挂一张破坏性工具确认卡（不弹 modal）。"""
        from .tool_confirm_card import ToolConfirmCard
        card = ToolConfirmCard(payload)
        self._current_assistant = None
        await self.mount(card)
        self.scroll_end(animate=False)

    def finish_tool_call(self, tc_id: str, result: str) -> None:
        card = self._tool_cards.get(tc_id)
        if card:
            card.mark_done(result)

    def deny_tool_call(self, tc_id: str, reason: str) -> None:
        card = self._tool_cards.get(tc_id)
        if card:
            card.mark_denied(reason)

    def finalize_turn(self) -> None:
        self._current_assistant = None
        self._current_thinking = None

    def clear_all(self) -> None:
        self._current_assistant = None
        self._current_thinking = None
        self._tool_cards.clear()
        for child in list(self.children):
            child.remove()

    # ── 历史消息加载 ───────────────────────────────

    async def load_history(self, messages: list[dict]) -> None:
        self.clear_all()
        for m in messages:
            role = m.get("role")
            content = m.get("content") or ""
            if role == "user":
                await self.mount(MessageBubble("user", content))
            elif role == "assistant":
                if content:
                    await self.mount(MessageBubble("assistant", content))
                tool_calls_raw = m.get("tool_calls")
                if tool_calls_raw:
                    try:
                        tcs = json.loads(tool_calls_raw) if isinstance(tool_calls_raw, str) else tool_calls_raw
                    except Exception:
                        tcs = []
                    for tc in tcs or []:
                        tc_id = tc.get("id") or ""
                        fn = tc.get("function") or {}
                        name = fn.get("name") or tc.get("name") or "unknown"
                        args_raw = fn.get("arguments") or tc.get("arguments") or "{}"
                        if isinstance(args_raw, str):
                            try:
                                args = json.loads(args_raw) if args_raw.strip() else {}
                            except Exception:
                                args = {"_raw": args_raw}
                        else:
                            args = args_raw or {}
                        card = ToolCallCard(tc_id, name, args)
                        self._tool_cards[tc_id] = card
                        await self.mount(card)
            elif role == "tool":
                tc_id = m.get("tool_call_id") or ""
                card = self._tool_cards.get(tc_id)
                if card:
                    card.mark_done(content)
        self.scroll_end(animate=False)
