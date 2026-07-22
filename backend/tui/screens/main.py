"""
MainScreen：TUI 主屏（阶段 2 版）。

三面板布局；右侧 pane 通过 F3/F4/F5 切换（Files/Todos/Skills）。
包含：
- 会话列表（切换/新建/删除/重命名）
- ChatView 消息流 + streaming
- InputArea 输入
- ToolConfirmModal 破坏性工具确认弹框
- HelpModal 快捷键帮助
- Plan Mode 快捷键切换
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Static

from ..client import MengdieClient
from ..widgets.chat_view import ChatView
from ..widgets.files_pane import FilesPane, FilePreviewRequested
from ..widgets.input_area import InputArea, MessageSubmitted, AtTriggered
from ..widgets.session_list import (
    SessionDeleteRequested, SessionList, SessionRenameRequested, SessionSelected,
)
from ..widgets.skills_pane import SkillsPane
from ..widgets.status_bar import StatusBar
from ..widgets.todos_pane import TodosPane
from ..widgets.tool_confirm_card import ConfirmDecided

from .file_preview import FilePreviewModal
from .file_picker import FilePickerModal
from .help import HelpModal


class MainScreen(Screen):
    CSS_PATH = "../theme.tcss"

    BINDINGS = [
        Binding("ctrl+n",       "new_session",     "新建",     show=True),
        Binding("ctrl+c",       "interrupt",       "中断",     show=True, priority=True),
        Binding("ctrl+q",       "quit",            "退出",     show=True, priority=True),
        Binding("ctrl+p",       "toggle_plan",     "PlanMode", show=True),
        Binding("f2",           "focus_input",     "聚焦输入", show=False),
        Binding("f3",           "show_pane('files')",  "文件",  show=True),
        Binding("f4",           "show_pane('todos')",  "Todos", show=True),
        Binding("f5",           "show_pane('skills')", "技能",  show=True),
        Binding("question_mark", "help",           "帮助",     show=True),
        Binding("escape",       "focus_chat",      "退出输入", show=False),
    ]

    def __init__(self, client: MengdieClient, initial_session_id: str | None = None):
        super().__init__()
        self.client = client
        self.initial_session_id = initial_session_id
        self._current_session_id: str | None = None
        self._sessions_cache: list[dict] = []
        self._right_pane: str = "files"

    # ── 布局 ────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-body"):
            with Vertical(id="left-pane"):
                yield Static("[b]会话[/b]  [dim](Ctrl-N 新建)[/dim]", id="left-title")
                yield SessionList()
            with Vertical(id="center-pane"):
                yield ChatView()
                yield InputArea()
            with Vertical(id="right-pane"):
                yield Static("[b]文件[/b]  [dim](F3/F4/F5 切换)[/dim]", id="right-title")
                # 三个 pane 都 mount，用 display 属性控制可见性
                yield FilesPane()
                yield TodosPane()
                yield SkillsPane()
        yield StatusBar()

    # ── 生命周期 ────────────────────────────────────

    async def on_mount(self) -> None:
        # 默认只显示文件树
        self._apply_pane_visibility()
        self._refresh_status()
        await self._load_sessions()

        target = self.initial_session_id or (
            self._sessions_cache[0]["id"] if self._sessions_cache else None
        )
        if target is None:
            new_sess = await self.client.create_session("新会话")
            self._sessions_cache.insert(0, new_sess)
            self._session_list.load_sessions(self._sessions_cache, new_sess["id"])
            target = new_sess["id"]

        await self._switch_session(target)
        self.set_focus(self.query_one(InputArea))

    # ── property shortcuts ──────────────────────────

    @property
    def _session_list(self) -> SessionList:      return self.query_one(SessionList)
    @property
    def _chat(self) -> ChatView:                 return self.query_one(ChatView)
    @property
    def _status(self) -> StatusBar:              return self.query_one(StatusBar)
    @property
    def _input(self) -> InputArea:               return self.query_one(InputArea)
    @property
    def _files(self) -> FilesPane:               return self.query_one(FilesPane)
    @property
    def _todos(self) -> TodosPane:               return self.query_one(TodosPane)
    @property
    def _skills(self) -> SkillsPane:             return self.query_one(SkillsPane)
    @property
    def _right_title(self) -> Static:            return self.query_one("#right-title", Static)

    # ── helpers ────────────────────────────────────

    def _refresh_status(self) -> None:
        self._status.connected = self.client.is_ws_connected()
        sid = self._current_session_id
        for s in self._sessions_cache:
            if s["id"] == sid:
                self._status.session_title = s.get("title") or ""
                break

    def _apply_pane_visibility(self) -> None:
        """按当前选中的 right_pane 设置各 widget display。"""
        self._files.display = self._right_pane == "files"
        self._todos.display = self._right_pane == "todos"
        self._skills.display = self._right_pane == "skills"
        title_map = {
            "files":  "[b]文件[/b]  [dim](F3/F4/F5 切换)[/dim]",
            "todos":  "[b]Todos[/b]  [dim](F3/F4/F5 切换)[/dim]",
            "skills": "[b]技能[/b]  [dim](F3/F4/F5 切换)[/dim]",
        }
        self._right_title.update(title_map.get(self._right_pane, ""))

    async def _load_sessions(self) -> None:
        try:
            self._sessions_cache = await self.client.list_sessions()
        except Exception as e:
            await self._chat.add_error_message(f"加载会话列表失败：{e}")
            self._sessions_cache = []
        self._session_list.load_sessions(self._sessions_cache, self._current_session_id)

    async def _switch_session(self, session_id: str) -> None:
        await self.client.disconnect_ws()
        self._current_session_id = session_id

        # 加载历史
        try:
            history = await self.client.get_messages(session_id)
            await self._chat.load_history(history)
        except Exception as e:
            await self._chat.add_error_message(f"加载消息失败：{e}")

        # 绑定文件树到该会话
        self._files.bind_client(self.client, session_id)

        # 初始 plan_mode / todos / skills
        try:
            self._status.plan_mode = await self.client.get_plan_mode(session_id)
        except Exception:
            self._status.plan_mode = False
        try:
            todos = await self.client.get_todos(session_id)
            self._todos.set_todos(todos)
        except Exception:
            self._todos.set_todos([])
        try:
            skills = await self.client.list_skills()
            self._skills.set_skills(skills)
        except Exception:
            self._skills.set_skills([])

        # WS
        try:
            await self.client.connect_ws(
                session_id,
                on_event=self._on_ws_event,
                on_close=self._on_ws_closed,
            )
        except Exception as e:
            await self._chat.add_error_message(f"WebSocket 连接失败：{e}")

        self._session_list.load_sessions(self._sessions_cache, session_id)
        self._refresh_status()

    def _on_ws_closed(self) -> None:
        self.call_from_thread(self._refresh_status)

    # ── WS 事件分发 ─────────────────────────────────

    async def _on_ws_event(self, evt: dict[str, Any]) -> None:
        etype = evt.get("type")
        if etype == "thinking":
            await self._chat.append_thinking(evt.get("content", ""))
        elif etype == "content_delta":
            self._status.streaming = True
            await self._chat.append_content_delta(evt.get("content", ""))
        elif etype == "tool_call":
            await self._chat.add_tool_call(
                evt.get("id", ""), evt.get("name", "?"), evt.get("args") or {},
            )
        elif etype == "tool_result":
            self._chat.finish_tool_call(evt.get("id", ""), evt.get("content", ""))
        elif etype == "tool_denied":
            self._chat.deny_tool_call(evt.get("id", ""), evt.get("reason", ""))
        elif etype == "tool_confirm":
            # 内联卡片，不弹 modal
            await self._chat.add_confirm_card(evt)
        elif etype == "plan_mode_update":
            self._status.plan_mode = bool(evt.get("plan_mode"))
        elif etype == "todos_update":
            self._todos.set_todos(evt.get("todos") or [])
        elif etype == "session_title":
            for s in self._sessions_cache:
                if s["id"] == evt.get("session_id"):
                    s["title"] = evt.get("title") or s.get("title") or "新会话"
                    break
            self._session_list.load_sessions(self._sessions_cache, self._current_session_id)
            self._refresh_status()
        elif etype == "done":
            self._chat.finalize_turn()
            self._status.streaming = False
        elif etype == "error":
            await self._chat.add_error_message(evt.get("message", "未知错误"))
            self._status.streaming = False

    async def _handle_tool_confirm(self, payload: dict[str, Any]) -> None:
        """已废弃：现在走 ChatView.add_confirm_card 内联卡片。保留占位避免 import 混乱。"""
        await self._chat.add_confirm_card(payload)

    async def on_confirm_decided(self, evt: ConfirmDecided) -> None:
        """内联确认卡决定完 → 发给后端。"""
        try:
            await self.client.send_confirm(evt.tc_id, evt.decision, evt.extra)
        except Exception as e:
            await self._chat.add_error_message(f"确认发送失败：{e}")

    # ── 输入 & 会话操作 ─────────────────────────────

    async def on_message_submitted(self, evt: MessageSubmitted) -> None:
        content = evt.content

        # 特殊指令
        if content.startswith("/allow "):
            await self.client.send_confirm(content[7:].strip(), "allow")
            return
        if content.startswith("/deny "):
            await self.client.send_confirm(content[6:].strip(), "deny")
            return
        if content.startswith("/rename"):
            new_title = content[len("/rename"):].strip()
            if not new_title:
                await self._chat.add_system_message("用法：/rename 新标题")
                return
            if self._current_session_id:
                await self._do_rename(self._current_session_id, new_title)
                await self._chat.add_system_message(f"[已重命名为 “{new_title}”]")
            return
        if content == "/delete":
            await self._chat.add_system_message(
                "⚠  确认删除当前会话？输入 /delete confirm 二次确认（不可撤销）"
            )
            return
        if content == "/delete confirm":
            if self._current_session_id:
                target = self._current_session_id
                await self._chat.add_system_message("[正在删除…]")
                await self.on_session_delete_requested(SessionDeleteRequested(target))
            return

        # 普通消息
        await self._chat.add_user_message(content)
        self._status.streaming = True
        try:
            await self.client.send_message(content)
        except Exception as e:
            await self._chat.add_error_message(f"发送失败：{e}")
            self._status.streaming = False

    async def on_session_selected(self, evt: SessionSelected) -> None:
        if evt.session_id == self._current_session_id:
            return
        await self._switch_session(evt.session_id)

    async def on_session_delete_requested(self, evt: SessionDeleteRequested) -> None:
        try:
            await self.client.delete_session(evt.session_id)
        except Exception as e:
            await self._chat.add_error_message(f"删除失败：{e}")
            return
        self._sessions_cache = [s for s in self._sessions_cache if s["id"] != evt.session_id]
        if evt.session_id == self._current_session_id:
            if self._sessions_cache:
                await self._switch_session(self._sessions_cache[0]["id"])
            else:
                await self.action_new_session()
        else:
            self._session_list.load_sessions(self._sessions_cache, self._current_session_id)

    async def on_session_rename_requested(self, evt: SessionRenameRequested) -> None:
        # 会话列表按 r：切到该会话并提示使用 /rename 指令
        if evt.session_id != self._current_session_id:
            await self._switch_session(evt.session_id)
        await self._chat.add_system_message("重命名当前会话请在输入框输入：/rename 新标题")

    async def _do_rename(self, session_id: str, new_title: str) -> None:
        try:
            await self.client.rename_session(session_id, new_title)
        except Exception as e:
            await self._chat.add_error_message(f"重命名失败：{e}")
            return
        for s in self._sessions_cache:
            if s["id"] == session_id:
                s["title"] = new_title
                break
        self._session_list.load_sessions(self._sessions_cache, self._current_session_id)
        self._refresh_status()

    async def on_file_preview_requested(self, evt: FilePreviewRequested) -> None:
        if self._current_session_id is None:
            return
        # 图片等二进制文件：TUI 无法真实预览，给个提示
        ext = evt.path.rsplit(".", 1)[-1].lower() if "." in evt.path else ""
        if ext in {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico", "avif",
                   "pdf", "zip", "tar", "gz", "mp4", "mov", "mp3"}:
            await self._chat.add_system_message(
                f"⚠  终端无法预览「{evt.path}」（二进制/媒体文件），请到 web UI 查看"
            )
            return
        try:
            data = await self.client.get_file_content(self._current_session_id, evt.path)
        except Exception as e:
            await self._chat.add_error_message(f"读取文件失败：{e}")
            return
        await self.app.push_screen(FilePreviewModal(
            path=evt.path,
            content=data.get("content", ""),
            truncated=bool(data.get("truncated")),
        ))

    async def on_at_triggered(self, evt: AtTriggered) -> None:
        """输入区 @ 触发文件选择器。"""
        if self._current_session_id is None:
            return

        def _cb(path: str | None) -> None:
            if path:
                self._input.insert_path(path)
            # 无论成功与否都聚焦回输入框
            self.set_focus(self._input)

        await self.app.push_screen(
            FilePickerModal(self.client, self._current_session_id, evt.initial_query),
            _cb,
        )

    # ── action 快捷键 ───────────────────────────────

    async def action_new_session(self) -> None:
        try:
            new_sess = await self.client.create_session("新会话")
        except Exception as e:
            await self._chat.add_error_message(f"创建会话失败：{e}")
            return
        self._sessions_cache.insert(0, new_sess)
        await self._switch_session(new_sess["id"])

    async def action_interrupt(self) -> None:
        if self._status.streaming:
            try:
                await self.client.send_stop()
                await self._chat.add_system_message("[已中断当前生成]")
            except Exception as e:
                await self._chat.add_error_message(f"中断失败：{e}")
            self._status.streaming = False
        else:
            self.app.exit()

    def action_focus_input(self) -> None:
        self.set_focus(self._input)

    def action_focus_chat(self) -> None:
        self.set_focus(self._chat)

    def action_quit(self) -> None:
        self.app.exit()

    def action_show_pane(self, pane: str) -> None:
        if pane not in ("files", "todos", "skills"):
            return
        self._right_pane = pane
        self._apply_pane_visibility()

    async def action_help(self) -> None:
        await self.app.push_screen(HelpModal())

    async def action_toggle_plan(self) -> None:
        if self._current_session_id is None:
            return
        new_val = not self._status.plan_mode
        try:
            await self.client.set_plan_mode(self._current_session_id, new_val)
            self._status.plan_mode = new_val
            await self._chat.add_system_message(
                f"[Plan Mode {'开启' if new_val else '关闭'}]",
            )
        except Exception as e:
            await self._chat.add_error_message(f"切换 Plan Mode 失败：{e}")
