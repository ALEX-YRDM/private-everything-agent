"""SubAgentBlock：主 Agent 派发 subagent 时的嵌套渲染。

- 一个 SubAgentBlock 对应一个 subagent_id
- 内部收集 subagent_event（thinking / tool_call / tool_result /
  content_delta）追加到 RichLog
- subagent_done 收到后展示最终结果
- 支持 focus + Enter → 弹出完整详情
"""
from __future__ import annotations

import json
from typing import Any

from textual.binding import Binding
from textual.message import Message
from textual.widgets import RichLog


class SubAgentOpenRequested(Message):
    """请求打开该 subagent 的完整详情。"""

    def __init__(self, session_id: str, task: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.task = task


class SubAgentBlock(RichLog):
    """一个 subagent 的事件流嵌套显示卡片。"""

    DEFAULT_CSS = """
    SubAgentBlock {
        height: auto;
        max-height: 24;
        margin: 0 2;
        padding: 0 1;
        background: transparent;
        border: round $secondary 60%;
    }
    SubAgentBlock:focus { border: heavy $accent; }
    SubAgentBlock.-done   { border: round green 60%; }
    SubAgentBlock.-error  { border: round red 60%; }
    """

    BINDINGS = [
        Binding("enter", "open_detail", "查看详情", show=False),
    ]

    can_focus = True

    def __init__(self, subagent_id: str, task: str, session_id: str | None = None):
        super().__init__(markup=True, wrap=True, highlight=False, auto_scroll=False)
        self.subagent_id = subagent_id
        self.task = task
        self.session_id = session_id or ""
        self._current_content: str = ""  # 当前 assistant 累积内容（用于长 delta 合并）
        self._header()

    def _header(self) -> None:
        safe = str(self.task).replace("[", r"\[")
        preview = safe[:60] + ("…" if len(safe) > 60 else "")
        self.write(f"[cyan bold]▸ subagent[/cyan bold] [dim]({self.subagent_id[:8]})  ↵ 查看全部[/dim]")
        self.write(f"[dim]任务：[/dim]{preview}")
        self.write("")

    def action_open_detail(self) -> None:
        if self.session_id:
            self.post_message(SubAgentOpenRequested(self.session_id, self.task))

    def apply_event(self, evt: dict[str, Any]) -> None:
        """吃一个 subagent_event.event 内部事件。"""
        etype = evt.get("type")
        if etype == "content_delta":
            # 累积 delta，换行时 flush；否则至少每 200 字符 flush 一次
            self._current_content += evt.get("content", "")
            if "\n" in self._current_content or len(self._current_content) > 200:
                self._flush_current_content()
        elif etype == "thinking":
            # 简报显示 thinking 首行
            content = evt.get("content", "").strip().split("\n", 1)[0]
            if content:
                safe = content[:80].replace("[", r"\[")
                self.write(f"[magenta dim]▸ thinking: {safe}[/magenta dim]")
        elif etype == "tool_call":
            name = str(evt.get("name", "?")).replace("[", r"\[")
            self._flush_current_content()
            self.write(f"[yellow]▶ {name}[/yellow]")
        elif etype == "tool_result":
            # 结果只显示前 80 字符简报
            result = str(evt.get("content", "")).replace("\n", " ").strip()
            if len(result) > 80:
                result = result[:80] + "…"
            safe = result.replace("[", r"\[")
            self.write(f"[dim]  → {safe}[/dim]")
        elif etype == "done":
            # 子 loop 的 done —— 把最后没换行的 delta 也 flush 掉
            self._flush_current_content()
        elif etype == "error":
            self._flush_current_content()
            msg = str(evt.get("message", "")).replace("[", r"\[")
            self.write(f"[red]错误：{msg}[/red]")

    def _write_content_line(self, line: str) -> None:
        if line.strip():
            safe = line.replace("[", r"\[")
            self.write(safe)

    def _flush_current_content(self) -> None:
        if not self._current_content:
            return
        # 一次性刷入所有累积内容（可以包含换行）
        for line in self._current_content.split("\n"):
            self._write_content_line(line)
        self._current_content = ""

    def mark_done(self, result: str, error: str | None = None) -> None:
        self._flush_current_content()
        for s in ("done", "error"):
            self.remove_class(f"-{s}")
        if error:
            self.add_class("-error")
            safe = str(error).replace("[", r"\[")
            self.write(f"[red bold]✗ 失败：{safe}[/red bold]")
        else:
            self.add_class("-done")
            self.write("")
            # 结果只显示前 400 字符
            preview = str(result)
            if len(preview) > 400:
                preview = preview[:400] + "\n…[已截断]"
            safe = preview.replace("[", r"\[")
            self.write(f"[green bold]✓ 完成[/green bold]")
            for line in safe.split("\n"):
                self.write(f"[dim]{line}[/dim]")
