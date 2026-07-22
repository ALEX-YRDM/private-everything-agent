"""ChatView：消息流渲染 + streaming 处理。

关键设计选择：所有条目 widget 都基于 RichLog（而不是 Static）——
Textual 8.x 的 Static 在动态 mount + display 切换场景下会出现
visual=None 崩溃。RichLog 天生为 "append 内容" 设计，永远有有效 visual。
"""
from __future__ import annotations

import json
import re
from typing import Any

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import RichLog


# assistant content 里 <think>...</think>（DeepSeek-R1 / GLM-Z1 等把 reasoning
# 混在 content 中）的抽取。开放式（只有开标签没有闭标签）也按 thinking 处理，
# 兼容流式期间正文还没到的情况。
_THINK_RE = re.compile(r"<think>([\s\S]*?)(?:</think>|$)", re.IGNORECASE)


def _split_think(raw: str) -> tuple[str, str]:
    """(thinking, body) —— 从 raw 里抽出所有 <think> 段落。"""
    if not raw or "<think>" not in raw.lower():
        return "", raw or ""
    chunks: list[str] = []

    def _sub(m: re.Match) -> str:
        chunks.append(m.group(1))
        return ""

    body = _THINK_RE.sub(_sub, raw)
    body = re.sub(r"</think>", "", body, flags=re.IGNORECASE)
    return "\n\n".join(c.strip() for c in chunks if c.strip()).strip(), body.strip()


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
    """一条消息 = 一个 widget。

    streaming 时使用 delta 缓冲：每次 append() 只累积到 _pending，
    真正 refresh 由 batch flush timer 触发（60ms 一次）；避免高频
    markdown 重渲染造成的卡顿。
    """

    ROLE_STYLE = {
        "user":      ("cyan bold",    "▎ 你"),
        "assistant": ("green bold",   "▎ 梦蝶"),
        "system":    ("yellow",       "▎ system"),
        "thinking":  ("magenta dim",  "▎ thinking"),
        "error":     ("red bold",     "▎ 错误"),
    }

    #: 缓冲刷新周期（秒）
    FLUSH_INTERVAL = 0.06

    def __init__(self, role: str, content: str = ""):
        super().__init__()
        self.role = role
        self._raw = content
        self._pending: str = ""
        self._flush_timer = None
        self.add_class(f"-{role}")
        self._refresh()

    def set_content(self, content: str) -> None:
        self._raw = content
        self._pending = ""
        self._refresh()

    def append(self, delta: str) -> None:
        self._pending += delta
        # 定时器还没起就起一个；已经起了就等下一 tick
        if self._flush_timer is None:
            self._flush_timer = self.set_interval(self.FLUSH_INTERVAL, self._flush)

    def _flush(self) -> None:
        if not self._pending:
            return
        self._raw += self._pending
        self._pending = ""
        self._refresh()

    def stop_streaming(self) -> None:
        """由 ChatView.finalize_turn 调用，flush 最后一次并停 timer。"""
        self._flush()
        if self._flush_timer is not None:
            self._flush_timer.stop()
            self._flush_timer = None

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
            return

        # assistant：先把 <think>...</think> 抽出来单独渲染成 magenta 段
        thinking, body = _split_think(text)
        if thinking:
            first_line = thinking.split("\n", 1)[0]
            preview = first_line[:120].replace("[", r"\[")
            ellipsis = "…" if len(thinking) > 120 else ""
            self.write(f"[magenta dim italic]▸ think: {preview}{ellipsis}[/magenta dim italic]")
            self.write("")
        if body:
            try:
                self.write(Markdown(body, code_theme="monokai"))
            except Exception:
                self.write(body.replace("[", r"\["))


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

    # 距底部这么多行内算"粘在底部"（给一点余量，避免抖动）
    _STICK_EPSILON = 2

    def __init__(self):
        super().__init__()
        self._current_assistant: MessageBubble | None = None
        self._current_thinking: ThinkingBlock | None = None
        self._tool_cards: dict[str, ToolCallCard] = {}
        # subagent_id → SubAgentBlock
        self._subagents: dict[str, Any] = {}

    # ── 粘底控制 ────────────────────────────────────

    def _is_at_bottom(self) -> bool:
        """当前视图是否已经贴在底部（用户没有向上翻阅历史）。"""
        try:
            return (self.max_scroll_y - self.scroll_y) <= self._STICK_EPSILON
        except Exception:
            return True

    def _follow_if_stuck(self, was_stuck: bool) -> None:
        """挂载新内容前记录 was_stuck；这里根据它决定是否跟随。"""
        if was_stuck:
            self.scroll_end(animate=False)

    def watch_virtual_size(self, old_size, new_size) -> None:
        """
        内容自身变高时（例如 MessageBubble 的 batch flush 让气泡长高），
        只有变化前视图就贴着底才跟随；用户往上翻的场景不打断。
        """
        if not old_size or not new_size:
            return
        if new_size.height <= old_size.height:
            return
        try:
            old_max = max(0, old_size.height - self.size.height)
            if self.scroll_y >= old_max - self._STICK_EPSILON:
                self.scroll_end(animate=False)
        except Exception:
            pass

    # ── 消息追加接口 ───────────────────────────────

    async def add_user_message(self, content: str) -> None:
        self._current_assistant = None
        self._current_thinking = None
        stick = self._is_at_bottom()
        bubble = MessageBubble("user", content)
        await self.mount(bubble)
        self._follow_if_stuck(stick)

    async def add_system_message(self, content: str) -> None:
        stick = self._is_at_bottom()
        bubble = MessageBubble("system", content)
        await self.mount(bubble)
        self._follow_if_stuck(stick)

    async def add_error_message(self, content: str) -> None:
        stick = self._is_at_bottom()
        bubble = MessageBubble("error", content)
        await self.mount(bubble)
        self._follow_if_stuck(stick)

    async def append_thinking(self, delta: str) -> None:
        stick = self._is_at_bottom()
        if self._current_thinking is None:
            self._current_thinking = ThinkingBlock()
            await self.mount(self._current_thinking)
        self._current_thinking.append(delta)
        self._follow_if_stuck(stick)

    async def append_content_delta(self, delta: str) -> None:
        stick = self._is_at_bottom()
        if self._current_assistant is None:
            self._current_assistant = MessageBubble("assistant", "")
            await self.mount(self._current_assistant)
        self._current_assistant.append(delta)
        # 首次 mount 后要显式跟一下；后续 batch flush 由 watch_virtual_size 兜底
        self._follow_if_stuck(stick)

    async def add_tool_call(self, tc_id: str, name: str, args: dict) -> None:
        stick = self._is_at_bottom()
        card = ToolCallCard(tc_id, name, args)
        self._tool_cards[tc_id] = card
        self._current_assistant = None
        await self.mount(card)
        self._follow_if_stuck(stick)

    async def add_confirm_card(self, payload: dict) -> None:
        """内联挂一张破坏性工具确认卡（不弹 modal）。

        破坏性工具确认必须让用户看见 → 无论用户是否在底部都强制滚到最下。
        """
        import asyncio
        from .tool_confirm_card import ToolConfirmCard
        card = ToolConfirmCard(payload)
        self._current_assistant = None
        await self.mount(card)
        await asyncio.sleep(0)
        self.scroll_end(animate=False, force=True)

    async def start_subagent(self, subagent_id: str, task: str, session_id: str = "") -> None:
        from .subagent_block import SubAgentBlock
        stick = self._is_at_bottom()
        block = SubAgentBlock(subagent_id, task, session_id)
        self._subagents[subagent_id] = block
        self._current_assistant = None
        await self.mount(block)
        self._follow_if_stuck(stick)

    def apply_subagent_event(self, subagent_id: str, event: dict) -> None:
        block = self._subagents.get(subagent_id)
        if block is not None:
            block.apply_event(event)
            # 不再无条件 scroll_end —— block 变高时 watch_virtual_size 会兜底

    def finish_subagent(self, subagent_id: str, result: str, error: str | None = None) -> None:
        block = self._subagents.get(subagent_id)
        if block is not None:
            block.mark_done(result, error)

    def finish_tool_call(self, tc_id: str, result: str) -> None:
        card = self._tool_cards.get(tc_id)
        if card:
            card.mark_done(result)

    def deny_tool_call(self, tc_id: str, reason: str) -> None:
        card = self._tool_cards.get(tc_id)
        if card:
            card.mark_denied(reason)

    def finalize_turn(self) -> None:
        # 停止 streaming 的 flush timer，把最后一批 delta 推出去
        if self._current_assistant is not None:
            try:
                self._current_assistant.stop_streaming()
            except Exception:
                pass
        if self._current_thinking is not None:
            # thinking block 现在也有 append，但没批量 flush；无需特殊处理
            pass
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
        # 加载完历史后统一滚到底部；这是"打开会话"场景，用户预期看到最新
        self.scroll_end(animate=False)
