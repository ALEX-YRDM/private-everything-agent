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
from ..widgets.attachment_strip import (
    Attachment, AttachmentStrip, AttachmentsChanged,
    build_from_clipboard, build_from_path,
)
from ..widgets.chat_view import ChatView
from ..widgets.files_pane import FilesPane, FilePreviewRequested
from ..widgets.input_area import (
    AtTriggered, InputArea, MessageSubmitted, PasteTextRequested,
)
from ..widgets.scheduler_pane import (
    SchedulerDeleteRequested, SchedulerPane, SchedulerRefreshRequested,
    SchedulerRunNowRequested, SchedulerToggleRequested,
)
from ..widgets.session_list import (
    SessionDeleteRequested, SessionList, SessionRenameRequested, SessionSelected,
)
from ..widgets.skills_pane import SkillsPane, SkillPreviewRequested
from ..widgets.slash_popup import SlashPopup
from ..widgets.subagent_block import SubAgentOpenRequested
from ..widgets.mcp_pane import MCPPane, MCPReconnectRequested, MCPToggleRequested
from ..widgets.status_bar import StatusBar
from ..widgets.todos_pane import TodosPane
from ..widgets.tool_confirm_card import ConfirmDecided
from ..widgets.trusts_pane import (
    TrustDeleteRequested, TrustsPane, TrustsPaneRefreshRequested,
)

from .file_preview import FilePreviewModal
from .file_picker import FilePickerModal
from .help import HelpModal
from .palette import CommandPalette
from .settings import SettingsScreen
from .skill_detail import SkillDetailModal
from .subagent_detail import SubAgentDetailModal
from .working_dir import WorkingDirPickerModal


class MainScreen(Screen):
    CSS_PATH = "../theme.tcss"

    BINDINGS = [
        Binding("ctrl+n",       "new_session",     "新建",     show=True),
        Binding("ctrl+c",       "interrupt",       "中断",     show=True, priority=True),
        Binding("ctrl+q",       "quit",            "退出",     show=True, priority=True),
        Binding("ctrl+f",       "palette",         "搜会话",   show=True, priority=True),
        Binding("ctrl+b",       "toggle_plan",     "PlanMode", show=True),
        Binding("ctrl+k",       "open_settings",   "设置",     show=True),
        Binding("ctrl+w",       "open_cwd_picker", "工作目录", show=True),
        Binding("ctrl+backslash", "toggle_left",   "左栏",     show=True),
        Binding("ctrl+right_square_bracket", "toggle_right", "右栏", show=True),
        Binding("f2",           "focus_input",     "聚焦输入", show=False),
        Binding("f3",           "show_pane('files')",  "文件",  show=True),
        Binding("f4",           "show_pane('todos')",  "Todos", show=True),
        Binding("f5",           "show_pane('skills')", "技能",  show=True),
        Binding("f6",           "show_pane('mcp')",    "MCP",   show=True),
        Binding("f7",           "show_pane('trusts')", "Trust", show=True),
        Binding("f8",           "show_pane('tasks')",  "定时",  show=True),
        Binding("f12",          "toggle_select_mode", "选择",   show=True),
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
        self._left_hidden: bool = False
        self._right_hidden: bool = False
        self._select_mode: bool = False

    # ── 布局 ────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-body"):
            with Vertical(id="left-pane"):
                yield Static("[b]会话[/b]  [dim](Ctrl-N 新建)[/dim]", id="left-title")
                yield SessionList()
            with Vertical(id="center-pane"):
                yield ChatView()
                with Vertical(id="input-container"):
                    yield SlashPopup()
                    yield AttachmentStrip()
                    yield InputArea()
            with Vertical(id="right-pane"):
                yield Static("[b]文件[/b]  [dim](F3/F4/F5/F6/F7/F8 切换)[/dim]", id="right-title")
                # 全部 mount，用 display 属性控制可见性
                yield FilesPane()
                yield TodosPane()
                yield SkillsPane()
                yield MCPPane()
                yield TrustsPane()
                yield SchedulerPane()
        yield StatusBar()

    # ── 生命周期 ────────────────────────────────────

    async def on_mount(self) -> None:
        # 默认只显示文件树
        self._apply_pane_visibility()

        # 绑定 slash popup 到 InputArea
        try:
            self.query_one(InputArea).bind_slash_popup(self.query_one(SlashPopup))
        except Exception:
            pass

        # 拉一次全局 config 拿到当前 model（会话专属 model 后续再覆盖）
        try:
            cfg = await self.client.get_config()
            self._status.model = cfg.get("model") or ""
        except Exception:
            pass

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
    def _attach_strip(self) -> AttachmentStrip:  return self.query_one(AttachmentStrip)
    @property
    def _files(self) -> FilesPane:               return self.query_one(FilesPane)
    @property
    def _todos(self) -> TodosPane:               return self.query_one(TodosPane)
    @property
    def _skills(self) -> SkillsPane:             return self.query_one(SkillsPane)
    @property
    def _mcp(self) -> MCPPane:                   return self.query_one(MCPPane)
    @property
    def _trusts(self) -> TrustsPane:             return self.query_one(TrustsPane)
    @property
    def _tasks(self) -> SchedulerPane:           return self.query_one(SchedulerPane)
    @property
    def _right_title(self) -> Static:            return self.query_one("#right-title", Static)

    # ── helpers ────────────────────────────────────

    def _refresh_status(self) -> None:
        self._status.connected = self.client.is_ws_connected()
        sid = self._current_session_id
        for s in self._sessions_cache:
            if s["id"] == sid:
                self._status.session_title = s.get("title") or ""
                # 有会话专属 model 就用它，否则不变
                if s.get("model"):
                    self._status.model = s["model"]
                break

    def _apply_pane_visibility(self) -> None:
        """按当前选中的 right_pane 设置各 widget display。"""
        self._files.display = self._right_pane == "files"
        self._todos.display = self._right_pane == "todos"
        self._skills.display = self._right_pane == "skills"
        self._mcp.display = self._right_pane == "mcp"
        self._trusts.display = self._right_pane == "trusts"
        self._tasks.display = self._right_pane == "tasks"
        title_map = {
            "files":  "[b]文件[/b]  [dim](F3-F8 切换)[/dim]",
            "todos":  "[b]Todos[/b]  [dim](F3-F8 切换)[/dim]",
            "skills": "[b]技能[/b]  [dim](F3-F8 · Enter 详情)[/dim]",
            "mcp":    "[b]MCP[/b]  [dim](F3-F8 · Enter 重连 · t 开关)[/dim]",
            "trusts": "[b]信任[/b]  [dim](Del 删除 · r 刷新)[/dim]",
            "tasks":  "[b]定时任务[/b]  [dim](t 开关 · r 立即执行 · d 删)[/dim]",
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
        elif etype == "subagent_start":
            await self._chat.start_subagent(
                evt.get("subagent_id", ""),
                evt.get("task", ""),
                evt.get("session_id", ""),
            )
        elif etype == "subagent_event":
            self._chat.apply_subagent_event(
                evt.get("subagent_id", ""),
                evt.get("event") or {},
            )
        elif etype == "subagent_done":
            self._chat.finish_subagent(
                evt.get("subagent_id", ""),
                evt.get("result", ""),
                evt.get("error"),
            )
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
        # 附件相关
        if content.startswith("/paste-img") or content.startswith("/paste"):
            # 从剪贴板追加一张图到附件区（不立即发送）
            rest = ""
            if content.startswith("/paste-img"):
                rest = content[len("/paste-img"):].strip()
            elif content.startswith("/paste"):
                rest = content[len("/paste"):].strip()
            self._append_clipboard_image()
            if rest:
                # 把余下的文字回填到输入框
                self._input.text = rest
            return
        if content == "/attach-clear":
            self._attach_strip.clear_items()
            await self._chat.add_system_message("[已清空附件]")
            return
        if content.startswith("/attach"):
            rest = content[len("/attach"):].strip()
            if not rest:
                await self._chat.add_system_message(
                    "用法：/attach <path>  支持 glob 和逗号分隔多个 pattern"
                )
                return
            self._append_paths_glob(rest)
            return
        if content.startswith("/copy"):
            arg = content[len("/copy"):].strip() or "last"
            await self._copy_last(arg)
            return
        if content.startswith("/export"):
            arg = content[len("/export"):].strip() or "md"
            await self._export_session(arg)
            return
        if content.startswith("/cwd"):
            arg = content[len("/cwd"):].strip()
            if not arg:
                await self._open_working_dir_picker()
                return
            await self._set_working_dir(arg)
            return
        if content.startswith("/model"):
            arg = content[len("/model"):].strip()
            if not arg:
                await self.action_open_settings()
                return
            await self._set_session_model(arg)
            return
        if content == "/trusts":
            await self._show_trusts()
            return

        # 普通消息 —— 带上附件（如果有）
        atts = self._attach_strip.items
        images = [a.data_uri for a in atts if a.image and a.data_uri]
        files_payload: list[dict] = []
        for a in atts:
            if a.image:
                continue
            if a.data_uri is None:
                continue
            files_payload.append({
                "name": a.label,
                "mime_type": a.mime_type or "application/octet-stream",
                "content": a.data_uri,  # base64
                "size": a.size,
            })

        await self._chat.add_user_message(
            content + (f"\n[附件 {len(atts)}]" if atts else "")
        )
        self._status.streaming = True
        try:
            await self.client.send_message(
                content,
                images=images or None,
                files=files_payload or None,
            )
        except Exception as e:
            await self._chat.add_error_message(f"发送失败：{e}")
            self._status.streaming = False
        finally:
            # 发送后清空附件区
            self._attach_strip.clear_items()

    def _append_clipboard_image(self) -> None:
        att = build_from_clipboard()
        if att is None:
            asyncio.create_task(self._chat.add_error_message(
                "剪贴板里没有图片，或未安装 pngpaste (macOS) / xclip (Linux)"
            ))
            return
        # 给同名 clipboard.png 加序号避免重复
        idx = sum(1 for a in self._attach_strip.items if a.label.startswith("clipboard")) + 1
        att.label = f"clipboard-{idx}.png"
        self._attach_strip.add(att)

    def _append_paths_glob(self, arg: str) -> None:
        """支持 glob 和逗号分隔多个 pattern。"""
        import glob as _glob
        from pathlib import Path

        patterns = [p.strip() for p in arg.split(",") if p.strip()]
        added: list[Attachment] = []
        missed: list[str] = []
        for pat in patterns:
            expanded = str(Path(pat).expanduser())
            matches = _glob.glob(expanded, recursive=True)
            if not matches:
                # 直接当路径试一下
                if Path(expanded).is_file():
                    matches = [expanded]
            if not matches:
                missed.append(pat)
                continue
            for m in sorted(matches):
                if not Path(m).is_file():
                    continue
                att = build_from_path(m)
                if att is not None:
                    added.append(att)
        if added:
            self._attach_strip.add_many(added)
        parts = []
        if added:
            parts.append(f"[已追加 {len(added)} 个附件]")
        if missed:
            parts.append(f"[未匹配：{', '.join(missed)}]")
        if parts:
            asyncio.create_task(self._chat.add_system_message(" ".join(parts)))

    async def _copy_last(self, arg: str) -> None:
        """把最新一条 assistant 消息复制到系统剪贴板。"""
        import shutil
        import subprocess
        import sys

        if self._current_session_id is None:
            return
        try:
            msgs = await self.client.get_messages(self._current_session_id)
        except Exception as e:
            await self._chat.add_error_message(f"读取历史失败：{e}")
            return
        text = ""
        for m in reversed(msgs):
            if m.get("role") == "assistant" and (m.get("content") or "").strip():
                text = m["content"]
                break
        if not text:
            await self._chat.add_system_message("[没有可复制的 assistant 消息]")
            return

        cmd: list[str] | None = None
        if sys.platform == "darwin" and shutil.which("pbcopy"):
            cmd = ["pbcopy"]
        elif shutil.which("wl-copy"):
            cmd = ["wl-copy"]
        elif shutil.which("xclip"):
            cmd = ["xclip", "-selection", "clipboard"]
        if cmd is None:
            await self._chat.add_error_message(
                "找不到 pbcopy/wl-copy/xclip；无法复制到系统剪贴板"
            )
            return
        try:
            p = subprocess.run(cmd, input=text.encode("utf-8"), timeout=5)
            if p.returncode == 0:
                await self._chat.add_system_message(f"[已复制 {len(text)} 字节到剪贴板]")
            else:
                await self._chat.add_error_message("复制失败（子进程返回非 0）")
        except Exception as e:
            await self._chat.add_error_message(f"复制失败：{e}")

    async def _export_session(self, fmt: str) -> None:
        """把当前会话 dump 成 markdown（简版）。"""
        from pathlib import Path

        if self._current_session_id is None:
            return
        try:
            msgs = await self.client.get_messages(self._current_session_id)
        except Exception as e:
            await self._chat.add_error_message(f"读取历史失败：{e}")
            return
        lines: list[str] = [f"# 梦蝶导出 · {self._current_session_id[:8]}", ""]
        for m in msgs:
            role = m.get("role")
            content = m.get("content") or ""
            if role == "user":
                lines.append(f"## 用户\n\n{content}\n")
            elif role == "assistant":
                lines.append(f"## 梦蝶\n\n{content}\n")
            elif role == "tool":
                lines.append(f"### 工具结果 ({m.get('name','?')})\n\n```\n{content}\n```\n")
        out_path = Path.home() / f"mengdie-export-{self._current_session_id[:8]}.md"
        try:
            out_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            await self._chat.add_error_message(f"写入失败：{e}")
            return
        await self._chat.add_system_message(f"[已导出到 {out_path}]")

    async def _show_trusts(self) -> None:
        if self._current_session_id is None:
            return
        try:
            r = await self.client.http.get(
                f"/api/sessions/{self._current_session_id}/trusts"
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            await self._chat.add_error_message(f"读取 trusts 失败：{e}")
            return
        paths = data.get("paths") or []
        cmds = data.get("commands") or []
        lines = ["已信任目录："]
        lines.extend([f"  · {p}" for p in paths] or ["  (无)"])
        lines.append("已信任命令前缀：")
        lines.extend([f"  · {c}" for c in cmds] or ["  (无)"])
        await self._chat.add_system_message("\n".join(lines))

    async def _set_working_dir(self, path: str) -> None:
        if self._current_session_id is None:
            return
        try:
            r = await self.client.http.put(
                f"/api/sessions/{self._current_session_id}/working-dir",
                json={"working_dir": path or None},
            )
            r.raise_for_status()
        except Exception as e:
            await self._chat.add_error_message(f"设置 cwd 失败：{e}")
            return
        # 更新缓存 + 重新 bind 文件树
        for s in self._sessions_cache:
            if s["id"] == self._current_session_id:
                s["working_dir"] = path or None
                break
        self._files.bind_client(self.client, self._current_session_id)
        await self._chat.add_system_message(f"[工作目录 → {path or '(默认 workspace)'}]")

    async def _open_working_dir_picker(self) -> None:
        cur = None
        for s in self._sessions_cache:
            if s["id"] == self._current_session_id:
                cur = s.get("working_dir") or ""
                break

        def _cb(new_path: str | None) -> None:
            if new_path is None:
                return
            asyncio.create_task(self._set_working_dir(new_path))

        await self.app.push_screen(WorkingDirPickerModal(cur or ""), _cb)

    async def _set_session_model(self, model_id: str) -> None:
        if self._current_session_id is None:
            return
        try:
            r = await self.client.http.put(
                f"/api/sessions/{self._current_session_id}/model",
                json={"model": model_id},
            )
            r.raise_for_status()
        except Exception as e:
            await self._chat.add_error_message(f"设置会话模型失败：{e}")
            return
        for s in self._sessions_cache:
            if s["id"] == self._current_session_id:
                s["model"] = model_id
                break
        self._status.model = model_id
        await self._chat.add_system_message(f"[本会话模型 → {model_id}]")

    async def _send_clipboard_image(self, prompt: str) -> None:
        """/paste-img [附言] —— 从剪贴板拿图 + 可选文字，一并发送。（保留兼容）"""
        att = build_from_clipboard()
        if att is None:
            await self._chat.add_error_message(
                "剪贴板里没有图片，或未安装 pngpaste (macOS) / xclip (Linux)"
            )
            return
        text = prompt or "（剪贴板图片）"
        await self._chat.add_user_message(text)
        self._status.streaming = True
        try:
            await self.client.send_message(text, images=[att.data_uri])
        except Exception as e:
            await self._chat.add_error_message(f"发送失败：{e}")
            self._status.streaming = False

    async def on_paste_text_requested(self, evt: PasteTextRequested) -> None:
        """输入区粘贴内容看起来像"多路径" → 转成附件；否则回填到输入框。"""
        raw = evt.raw or ""
        # 拆行 + 空格切；抓所有存在的文件路径
        from pathlib import Path
        candidates: list[str] = []
        for line in raw.replace("\t", "\n").splitlines():
            # 粗暴处理带空格的路径：先按空格切，逐段拼路径
            # 简化：如果整行是一个存在的文件，就用；否则退回按空格切
            line = line.strip().strip("'\"")
            if not line:
                continue
            if Path(line).expanduser().is_file():
                candidates.append(str(Path(line).expanduser()))
                continue
            for part in line.split():
                part = part.strip("'\"")
                if Path(part).expanduser().is_file():
                    candidates.append(str(Path(part).expanduser()))

        if not candidates:
            # 交回给输入框做正常粘贴
            self._input.insert(raw)
            return

        added: list[Attachment] = []
        for p in candidates:
            att = build_from_path(p)
            if att is not None:
                added.append(att)
        if added:
            self._attach_strip.add_many(added)
            await self._chat.add_system_message(f"[已通过粘贴追加 {len(added)} 个附件]")
        else:
            # 都不是可读文件，还回给输入框
            self._input.insert(raw)

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
        ext = evt.path.rsplit(".", 1)[-1].lower() if "." in evt.path else ""
        image_exts = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}
        binary_exts = {"pdf", "zip", "tar", "gz", "mp4", "mov", "mp3", "ico", "avif"}

        # 图片：内联渲染（若终端支持）；否则给提示
        if ext in image_exts:
            from ..imaging import detect_terminal, render_image_bytes
            kind = detect_terminal()
            if kind == "none":
                await self._chat.add_system_message(
                    f"⚠  当前终端不支持内联渲染「{evt.path}」，请到 web UI 查看"
                )
                return
            try:
                # 直接从后端拉原始二进制
                r = await self.client.http.get(
                    f"/api/sessions/{self._current_session_id}/file-raw",
                    params={"path": evt.path},
                )
                r.raise_for_status()
                seq = render_image_bytes(r.content)
            except Exception as e:
                await self._chat.add_error_message(f"读取图片失败：{e}")
                return
            if seq is None:
                await self._chat.add_system_message(
                    f"⚠  当前终端不支持内联渲染「{evt.path}」"
                )
                return
            # 把 iTerm2/kitty 转义序列作为普通文本写入 —— 系统消息里
            await self._chat.add_system_message(
                f"预览：{evt.path}\n{seq}"
            )
            return

        # 其他二进制：仍然拒绝预览
        if ext in binary_exts:
            await self._chat.add_system_message(
                f"⚠  终端无法预览「{evt.path}」（二进制/媒体文件）"
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

    async def on_skill_preview_requested(self, evt: SkillPreviewRequested) -> None:
        try:
            detail = await self.client.get_skill(evt.name)
        except Exception as e:
            await self._chat.add_error_message(f"读取 skill 失败：{e}")
            return
        await self.app.push_screen(SkillDetailModal(detail))

    async def on_sub_agent_open_requested(self, evt: SubAgentOpenRequested) -> None:
        try:
            msgs = await self.client.get_messages(evt.session_id)
        except Exception as e:
            await self._chat.add_error_message(f"读取子任务失败：{e}")
            return
        await self.app.push_screen(SubAgentDetailModal(evt.task, msgs))

    async def on_mcp_reconnect_requested(self, evt: MCPReconnectRequested) -> None:
        try:
            await self.client.reconnect_mcp(evt.server_id)
            await self._refresh_mcp()
        except Exception as e:
            await self._chat.add_error_message(f"MCP 重连失败：{e}")

    async def on_mcp_toggle_requested(self, evt: MCPToggleRequested) -> None:
        try:
            await self.client.toggle_mcp(evt.server_id)
            await self._refresh_mcp()
        except Exception as e:
            await self._chat.add_error_message(f"MCP 切换启用状态失败：{e}")

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
        if pane not in ("files", "todos", "skills", "mcp", "trusts", "tasks"):
            return
        self._right_pane = pane
        self._apply_pane_visibility()
        # 切到 MCP / Trusts / Tasks 时懒加载一次
        if pane == "mcp":
            asyncio.create_task(self._refresh_mcp())
        elif pane == "trusts":
            asyncio.create_task(self._refresh_trusts())
        elif pane == "tasks":
            asyncio.create_task(self._refresh_tasks())

    async def _refresh_mcp(self) -> None:
        try:
            servers = await self.client.list_mcp_servers()
            self._mcp.set_servers(servers)
        except Exception as e:
            await self._chat.add_error_message(f"加载 MCP 列表失败：{e}")

    async def _refresh_trusts(self) -> None:
        if self._current_session_id is None:
            return
        try:
            data = await self.client.get_trusts(self._current_session_id)
            self._trusts.set_data(
                data.get("paths") or [],
                data.get("commands") or [],
            )
        except Exception as e:
            await self._chat.add_error_message(f"加载信任列表失败：{e}")

    async def _refresh_tasks(self) -> None:
        try:
            tasks = await self.client.list_tasks()
            self._tasks.set_tasks(tasks)
        except Exception as e:
            await self._chat.add_error_message(f"加载定时任务失败：{e}")

    async def on_trust_delete_requested(self, evt: TrustDeleteRequested) -> None:
        if self._current_session_id is None:
            return
        try:
            await self.client.delete_trust(self._current_session_id, evt.kind, evt.value)
        except Exception as e:
            await self._chat.add_error_message(f"删除信任项失败：{e}")
            return
        await self._refresh_trusts()

    async def on_trusts_pane_refresh_requested(self, _evt: TrustsPaneRefreshRequested) -> None:
        await self._refresh_trusts()

    async def on_scheduler_toggle_requested(self, evt: SchedulerToggleRequested) -> None:
        try:
            await self.client.toggle_task(evt.task_id)
        except Exception as e:
            await self._chat.add_error_message(f"切换任务开关失败：{e}")
            return
        await self._refresh_tasks()

    async def on_scheduler_run_now_requested(self, evt: SchedulerRunNowRequested) -> None:
        try:
            await self.client.run_task_now(evt.task_id)
            await self._chat.add_system_message(f"[已触发任务 #{evt.task_id}]")
        except Exception as e:
            await self._chat.add_error_message(f"触发任务失败：{e}")

    async def on_scheduler_delete_requested(self, evt: SchedulerDeleteRequested) -> None:
        try:
            await self.client.delete_task(evt.task_id)
        except Exception as e:
            await self._chat.add_error_message(f"删除任务失败：{e}")
            return
        await self._refresh_tasks()

    async def on_scheduler_refresh_requested(self, _evt: SchedulerRefreshRequested) -> None:
        await self._refresh_tasks()

    async def action_help(self) -> None:
        await self.app.push_screen(HelpModal())

    async def action_palette(self) -> None:
        """Ctrl-P 弹会话快速搜索。"""
        def _cb(session_id: str | None) -> None:
            if session_id and session_id != self._current_session_id:
                asyncio.create_task(self._switch_session(session_id))

        await self.app.push_screen(
            CommandPalette(self._sessions_cache), _cb,
        )

    async def action_open_settings(self) -> None:
        """Ctrl-K 打开设置屏。"""
        try:
            cfg = await self.client.get_config()
            models = await self.client.list_models()
        except Exception as e:
            await self._chat.add_error_message(f"加载设置失败：{e}")
            return
        current = cfg.get("model") or ""

        # 找当前会话的 model
        session_model = None
        for s in self._sessions_cache:
            if s["id"] == self._current_session_id:
                session_model = s.get("model")
                break

        def _cb(result: dict | None) -> None:
            if not result:
                return
            model_id = result.get("model")
            scope = result.get("scope") or "global"
            if not model_id:
                return
            if scope == "session":
                asyncio.create_task(self._set_session_model(model_id))
            else:
                asyncio.create_task(self._switch_model(model_id))

        await self.app.push_screen(
            SettingsScreen(
                self.client, cfg, models, current,
                session_model=session_model,
                has_session=self._current_session_id is not None,
            ),
            _cb,
        )

    async def _switch_model(self, model_id: str) -> None:
        try:
            await self.client.switch_model(model_id)
            self._status.model = model_id
            await self._chat.add_system_message(f"[已切换模型 → {model_id}]")
        except Exception as e:
            await self._chat.add_error_message(f"切换模型失败：{e}")

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

    def action_toggle_left(self) -> None:
        self._left_hidden = not self._left_hidden
        self.query_one("#left-pane").display = not self._left_hidden

    async def action_open_cwd_picker(self) -> None:
        await self._open_working_dir_picker()

    def action_toggle_right(self) -> None:
        self._right_hidden = not self._right_hidden
        self.query_one("#right-pane").display = not self._right_hidden

    def action_toggle_select_mode(self) -> None:
        """F12 —— 关闭 Textual 鼠标捕获，让用户直接用终端选中复制。"""
        self._select_mode = not self._select_mode
        driver = getattr(self.app, "_driver", None)
        if driver is None:
            return
        try:
            if self._select_mode:
                driver.disable_mouse_support()
                self._status.hint = "SELECT MODE · 再按 F12 恢复"
            else:
                driver.enable_mouse_support()
                self._status.hint = ""
        except Exception:
            # 某些老终端 driver 不实现这两个方法，忽略
            self._status.hint = "此终端不支持选择模式切换"
