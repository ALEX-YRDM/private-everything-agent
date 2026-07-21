import asyncio
import json
import re as _re
from pathlib import Path
from loguru import logger

from ..providers.base import LLMProvider, StreamEvent
from ..tools.registry import ToolRegistry
from ..tools.context import ToolContext
from ..session.manager import SessionManager
from .confirmer import ConfirmationBroker
from .context import ContextBuilder
from .memory import MemoryManager


_THINK_RE = _re.compile(r"<think>.*?</think>", _re.DOTALL | _re.IGNORECASE)
_THINK_OPEN_RE = _re.compile(r"<think>.*", _re.DOTALL | _re.IGNORECASE)


def _strip_think_tags(text: str) -> str:
    """
    剥掉部分模型（DeepSeek-R1、GLM-Z1 等）写在 content 里的 <think>...</think> 块。
    - 完整成对的直接删；
    - 只有开标签没有闭标签（截断/未收尾）时，从 <think> 开始到末尾全丢；
    - 也兼容裸露的 </think>（去掉）。
    """
    if not text:
        return text
    low = text.lower()
    if "<think>" not in low and "</think>" not in low:
        return text
    stripped = _THINK_RE.sub("", text)
    stripped = _THINK_OPEN_RE.sub("", stripped)
    stripped = _re.sub(r"</think>", "", stripped, flags=_re.IGNORECASE)
    return stripped.strip()


class AgentLoop:
    """
    核心 ReAct 循环：
    用户输入 → 构建 Prompt → LLM → 工具调用 → LLM → ... → 最终回复

    支持：
    - 流式 token 输出（via AsyncGenerator）
    - 工具调用可视化事件
    - 自动记忆整合
    - MCP 工具
    - 最大迭代次数限制
    - SubAgent 模式（depth > 0）：并行派发、隔离执行、事件透传
    """

    TOOL_RESULT_MAX_CHARS = 40000

    # 按工具类型分档的截断上限（未列出的走 TOOL_RESULT_MAX_CHARS 默认值）
    # 读类工具需要看完整文件/搜索结果；执行类工具容易一次爆炸（find /、日志 tail）
    TOOL_RESULT_LIMITS = {
        "read_file":   40000,
        "read_skill":  40000,
        "grep":        20000,
        "glob":        15000,
        "list_dir":    15000,
        "exec":        10000,
        "web_fetch":   30000,
        "web_search":  15000,
    }

    @classmethod
    def _result_limit(cls, tool_name: str) -> int:
        return cls.TOOL_RESULT_LIMITS.get(tool_name, cls.TOOL_RESULT_MAX_CHARS)

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        session_manager: SessionManager,
        memory_manager: MemoryManager,
        context_builder: ContextBuilder,
        tools: ToolRegistry,
        model: str = "gpt-4o",
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        depth: int = 0,
        allowed_tools: list[str] | None = None,
        confirm_required_tools: set[str] | None = None,
    ):
        self.provider = provider
        self.workspace = workspace
        self.sessions = session_manager
        self.memory = memory_manager
        self.context = context_builder
        self.tools = tools
        self.model = model
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.confirm_required_tools = confirm_required_tools or set()
        # SubAgent 相关
        self.depth = depth                    # 0=主Agent，1+=SubAgent
        self.allowed_tools = allowed_tools    # 工具白名单（SubAgent 动态指定）
        self._current_session_id: str | None = None  # 当前处理的 session_id（供 SpawnSubAgentsTool 读取）
        self._current_ctx: ToolContext | None = None  # 当前工具执行上下文（供 SpawnSubAgentsTool 继承）
        # 后台任务强引用池：防止 asyncio.create_task 出来的 task 被 GC
        # https://docs.python.org/3/library/asyncio-task.html#creating-tasks
        self._background_tasks: set[asyncio.Task] = set()

    def _spawn_background(self, coro) -> asyncio.Task:
        """派发一个后台任务并持有强引用，防止 GC 提前中止。"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def _build_tool_ctx(self, session_id: str, session_row: dict | None, session_meta: dict) -> ToolContext:
        """从会话行 + metadata 构造 ToolContext。"""
        working_dir_raw = (session_row or {}).get("working_dir")
        if working_dir_raw:
            cwd = Path(working_dir_raw).expanduser().resolve()
            sandbox_mode = "free"  # 用户显式设置 working_dir → 完全放开
        else:
            cwd = self.workspace.resolve()
            sandbox_mode = "workspace"  # 老会话，保留原行为
        return ToolContext(
            cwd=cwd,
            session_id=session_id,
            sandbox_mode=sandbox_mode,
            trusted_paths=list(session_meta.get("trusted_paths") or []),
            trusted_commands=list(session_meta.get("trusted_commands") or []),
        )

    async def _get_or_probe(
        self, session_id: str, working_dir: Path | None, session_meta: dict,
    ) -> dict | None:
        """
        懒加载项目探测：缓存命中且 cwd 未变则复用；否则重新探测并写回 metadata。
        无 working_dir（老会话）则返回 None。
        """
        if not working_dir:
            return None
        cached = session_meta.get("project_probe") or {}
        if cached.get("cwd") == str(working_dir):
            return cached
        try:
            from .project_probe import probe as _probe
            result = await _probe(working_dir)
        except Exception as e:
            logger.warning(f"project_probe 失败（非致命）: {e}")
            return cached or None
        # 写回 metadata（不阻塞，但也不需要等待）
        new_meta = {**session_meta, "project_probe": result}
        try:
            await self.memory.db.set_session_metadata(session_id, new_meta)
        except Exception as e:
            logger.warning(f"写入 project_probe 缓存失败: {e}")
        return result

    # ── 确认协议辅助 ─────────────────────────────────────────────────────────

    def _is_trusted(self, tool_name: str, args: dict, ctx: ToolContext | None) -> bool:
        """判断此次工具调用是否已被会话级信任覆盖。"""
        if ctx is None:
            return False
        if tool_name == "exec":
            command = str(args.get("command", "")).lstrip()
            return self.sessions.is_command_trusted(command, ctx.trusted_commands)
        # 文件类工具：检查 path 是否在 trusted_paths 子树下
        if not ctx.trusted_paths:
            return False
        path = args.get("path")
        if not path:
            return False
        try:
            from ..tools.filesystem import _PathResolver
            resolved = _PathResolver.resolve(path, ctx)
        except Exception:
            return False
        return self.sessions.is_path_trusted(str(resolved), ctx.trusted_paths)

    def _build_confirm_payload(self, tool_name: str, args: dict, ctx: ToolContext | None) -> dict:
        """
        构造发给前端的 tool_confirm 事件 payload。
        含 name / args / cwd / why / preview（edit 类补 diff、exec 显示命令+cwd）。
        """
        cwd_str = str(ctx.cwd) if ctx else ""
        payload: dict = {
            "name": tool_name,
            "args": args,
            "cwd": cwd_str,
        }
        if tool_name == "exec":
            cmd = args.get("command", "")
            payload["why"] = "该工具会在 shell 中执行命令，可能读写文件系统或访问网络。"
            payload["preview"] = {"kind": "exec", "command": cmd, "cwd": cwd_str}
            # 前端可以从 preview 里提取 argv[0] 作为默认信任前缀
            first_token = cmd.strip().split(None, 1)[0] if cmd.strip() else ""
            payload["suggested_trust_command"] = first_token
        elif tool_name in ("write_file", "edit_file", "multi_edit"):
            payload["why"] = "该工具会写入 / 修改文件内容。"
            payload["preview"] = {"kind": "file", "path": args.get("path")}
            payload["suggested_trust_path"] = args.get("path")
        elif tool_name == "apply_patch":
            payload["why"] = "该工具会按 diff 补丁改动多个文件。"
            patch = args.get("patch", "")
            payload["preview"] = {"kind": "patch", "patch": patch[:4000]}
        else:
            payload["why"] = "破坏性工具，需要用户确认。"
        return payload

    def create_subagent_loop(self, allowed_tools: list[str] | None = None) -> "AgentLoop":
        """
        创建一个 SubAgent 用的 AgentLoop 实例，共享所有组件但：
        - depth + 1（防止无限递归）
        - max_iterations 上限为 20
        - allowed_tools 限定工具白名单
        """
        return AgentLoop(
            provider=self.provider,
            workspace=self.workspace,
            session_manager=self.sessions,
            memory_manager=self.memory,
            context_builder=self.context,
            tools=self.tools,
            model=self.model,
            max_iterations=min(20, self.max_iterations),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            depth=self.depth + 1,
            allowed_tools=allowed_tools,
            confirm_required_tools=self.confirm_required_tools,
        )

    async def process_stream(self, session_id: str, user_content: str, model: str | None = None, images: list[str] | None = None, files: list[dict] | None = None, confirmer: "ConfirmationBroker | None" = None):
        """
        处理用户消息，以异步生成器方式 yield 事件字典。

        事件类型（主 Agent）：
        - {"type": "thinking", "content": "..."}          LLM 推理过程
        - {"type": "tool_call", "name": "...", "args": {...}}   工具调用
        - {"type": "tool_result", "name": "...", "content": "..."} 工具结果
        - {"type": "tool_confirm", "id": ..., "name": ..., "args": ..., ...}  等待用户确认
        - {"type": "tool_denied", "id": ..., "name": ..., "reason": ...}  用户拒绝
        - {"type": "subagent_start", "subagent_id": "...", "session_id": "...", "task": "..."}
        - {"type": "subagent_event", "subagent_id": "...", "event": {...}}
        - {"type": "subagent_done", "subagent_id": "...", "result": "..."}
        - {"type": "content_delta", "content": "..."}     流式 token
        - {"type": "done", "content": "..."}              完成
        - {"type": "error", "message": "..."}             出错

        confirmer：ConfirmationBroker 实例；破坏性工具执行前 await
        broker.request(...) 得到用户决策。SubAgent 从父 loop 继承。
        """
        self._current_session_id = session_id
        self._current_confirmer = confirmer
        # 供 SpawnSubAgentsTool 读取当前 plan_mode（下方 non-subagent 分支会覆盖）
        self._current_plan_mode = False
        # SubAgent 场景下参数 confirmer 通常为空，从父 loop 继承（由 SpawnSubAgentsTool 注入）
        if confirmer is None:
            confirmer = getattr(self, "_inherited_confirmer", None)

        is_subagent = self.depth > 0

        if is_subagent:
            # SubAgent：简洁上下文，无历史，无记忆；从父 ctx 继承 cwd
            session_overrides: dict[str, bool] = {}
            effective_model = model or self.model
            should_generate_title = False
            ctx = self._current_ctx
            sub_working_dir = ctx.cwd if ctx else None
            # SubAgent 从父 loop 继承 plan_mode（父在 plan mode 时子任务也应受限）
            plan_mode = bool(getattr(self, "_inherited_plan_mode", False))
            self._current_plan_mode = plan_mode
            # SubAgent 场景下没有 session_meta，project_probe 若在父会话里可以额外传，
            # 但当前只需 cwd 简报即可
            messages = await self.context.build_subagent_messages(
                user_content, working_dir=sub_working_dir,
            )
        else:
            # 主 Agent：完整上下文
            history, session_row, session_meta = await asyncio.gather(
                self.sessions.get_history(session_id),
                self.sessions.get_session(session_id),
                self.memory.db.get_session_metadata(session_id),
            )
            should_generate_title = (session_row or {}).get("title") == "新会话"
            session_model = (session_row or {}).get("model") or None
            session_overrides = session_meta.get("tool_overrides", {})
            plan_mode = bool(session_meta.get("plan_mode"))
            self._current_plan_mode = plan_mode
            effective_model = model or session_model or self.model
            ctx = self._build_tool_ctx(session_id, session_row, session_meta)
            main_working_dir = ctx.cwd if (session_row or {}).get("working_dir") else None
            # 项目探测缓存：绑定到 cwd，cwd 变更时重新探测
            project_probe = await self._get_or_probe(
                session_id, main_working_dir, session_meta,
            )
            messages = await self.context.build_messages(
                history, user_content, session_id,
                images=images, files=files,
                working_dir=main_working_dir, project_probe=project_probe,
                plan_mode=plan_mode,
            )

        self._current_ctx = ctx

        # 查询模型专属参数（未设置则回落到实例级全局值）
        from ..providers.key_manager import get_model_params as _get_model_params
        _mparams = _get_model_params(effective_model)
        effective_max_tokens = _mparams.get("max_tokens") or self.max_tokens
        effective_context_window = _mparams.get("context_window_tokens") or None

        # 构建工具定义：SubAgent 排除 spawn_subagents 且应用白名单
        exclude = {"spawn_subagents"} if is_subagent else None
        allowed = set(self.allowed_tools) if self.allowed_tools else None
        tool_defs = self.tools.get_definitions(
            session_overrides=session_overrides,
            allowed_names=allowed,
            exclude_names=exclude,
        )

        new_messages: list[dict] = []
        final_content: str | None = None
        final_reasoning: str | None = None
        accumulated_content = ""
        _turn_saved = False   # 标记 save_turn 是否已在 try 块中提前完成

        try:
            for iteration in range(self.max_iterations):
                accumulated_content = ""
                tool_calls_ready = None
                current_iter_usage: dict | None = None  # 本次 LLM call 的 token 用量

                async for event in self.provider.chat_stream(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                    model=effective_model,
                    temperature=self.temperature,
                    max_tokens=effective_max_tokens,
                ):
                    if event.type == "content_delta":
                        accumulated_content += event.content
                        yield {"type": "content_delta", "content": event.content}

                    elif event.type == "thinking":
                        yield {"type": "thinking", "content": event.content}

                    elif event.type == "tool_call":
                        yield {"type": "tool_call", **event.data}

                    elif event.type == "tool_call_delta":
                        yield {"type": "tool_call_delta", **event.data}

                    elif event.type == "usage":
                        current_iter_usage = event.data

                    elif event.type == "tool_calls_ready":
                        tool_calls_ready = event.data
                        # 发送带完整参数的 tool_call 更新事件，让前端更新早先发出的空参数版本
                        for tc in tool_calls_ready.get("tool_calls", []):
                            yield {
                                "type": "tool_call",
                                "id": tc["id"],
                                "name": tc["name"],
                                "args": tc["arguments"],
                            }

                    elif event.type == "done":
                        final_content = event.content or accumulated_content
                        final_reasoning = (event.data or {}).get("reasoning_content")
                        break

                    elif event.type == "error":
                        from ..utils.errors import classify_error
                        raw = event.content or "未知错误"
                        # 用一个假异常构造分类结果（LiteLLM 已把错误变成字符串）
                        classified = classify_error(Exception(raw))
                        yield {
                            "type": "error",
                            "message": raw,
                            "category": classified.category,
                            "retriable": classified.retriable,
                            "hint": classified.hint,
                        }
                        return

                if tool_calls_ready:
                    tc_content = tool_calls_ready["content"]
                    tc_list = tool_calls_ready["tool_calls"]
                    tc_reasoning = tool_calls_ready.get("reasoning_content")

                    assistant_msg: dict = {
                        "role": "assistant",
                        "content": tc_content,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                                },
                            }
                            for tc in tc_list
                        ],
                    }
                    if tc_reasoning:
                        assistant_msg["reasoning_content"] = tc_reasoning
                    if current_iter_usage:
                        assistant_msg["input_tokens"] = current_iter_usage.get("input_tokens")
                        assistant_msg["output_tokens"] = current_iter_usage.get("output_tokens")
                    messages.append(assistant_msg)
                    new_messages.append(assistant_msg)

                    for tc in tc_list:
                        tool_obj = self.tools.get_tool(tc["name"])

                        # ── Plan Mode 拦截 ───────────────────────────────
                        # 处于 Plan Mode 时，所有破坏性工具直接拒绝执行。
                        # 每个 tool_call 之前重读 metadata（DB 读极轻），确保同一轮内
                        # Agent 通过 enter/exit_plan_mode 切换状态后能立即生效。
                        if not is_subagent and session_id:
                            try:
                                cur_meta = await self.memory.db.get_session_metadata(session_id)
                                self._current_plan_mode = bool(cur_meta.get("plan_mode"))
                            except Exception:
                                pass
                        if self._current_plan_mode and tc["name"] in self.confirm_required_tools:
                            reason = "当前处于 Plan Mode：请把方案与预期改动写在回复中；用户批准后关闭 Plan Mode 再实际执行。"
                            yield {
                                "type": "tool_denied", "id": tc["id"],
                                "name": tc["name"], "reason": reason,
                            }
                            tool_msg = {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "name": tc["name"],
                                "content": f"[Plan Mode] {reason}",
                            }
                            messages.append(tool_msg)
                            new_messages.append(tool_msg)
                            yield {"type": "tool_result", "id": tc["id"],
                                   "name": tc["name"], "content": tool_msg["content"]}
                            continue

                        # ── 破坏性工具确认 ────────────────────────────────
                        # 判定：工具名在 confirm_required_tools 中，且未被会话级
                        # trusted_paths / trusted_commands 覆盖。
                        needs_confirm = (
                            tc["name"] in self.confirm_required_tools
                            and confirmer is not None
                        )
                        if needs_confirm and self._is_trusted(tc["name"], tc["arguments"], ctx):
                            needs_confirm = False

                        if needs_confirm:
                            payload = self._build_confirm_payload(
                                tc["name"], tc["arguments"], ctx,
                            )
                            resp = await confirmer.request(tc["id"], payload)
                            if resp.decision == "deny":
                                reason = resp.extra or "用户已拒绝"
                                deny_msg = f"[已拒绝] {reason}"
                                yield {
                                    "type": "tool_denied",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "reason": reason,
                                }
                                # 作为 tool_result 反馈给 LLM，让下一轮知道
                                tool_msg = {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "name": tc["name"],
                                    "content": deny_msg,
                                }
                                messages.append(tool_msg)
                                new_messages.append(tool_msg)
                                yield {"type": "tool_result", "id": tc["id"], "name": tc["name"], "content": deny_msg}
                                continue  # 跳过后续执行
                            elif resp.decision == "trust_path" and resp.extra:
                                try:
                                    await self.sessions.add_trusted_path(session_id, resp.extra)
                                    ctx.trusted_paths.append(resp.extra)
                                except Exception as e:
                                    logger.warning(f"添加信任路径失败: {e}")
                            elif resp.decision == "trust_command" and resp.extra:
                                try:
                                    await self.sessions.add_trusted_command(session_id, resp.extra)
                                    ctx.trusted_commands.append(resp.extra)
                                except Exception as e:
                                    logger.warning(f"添加信任命令失败: {e}")
                            # allow / trust_path / trust_command 都继续执行

                        # 检查是否为 StreamingTool（如 spawn_subagents）
                        from ..tools.base import StreamingTool as _ST
                        if isinstance(tool_obj, _ST):
                            # 用 asyncio.Queue 桥接流式事件到主生成器
                            event_queue: asyncio.Queue = asyncio.Queue()

                            def make_sync_callback(q: asyncio.Queue):
                                def _cb(evt: dict):
                                    q.put_nowait(evt)
                                return _cb

                            sync_cb = make_sync_callback(event_queue)

                            async def run_streaming(tool=tool_obj, params=tc["arguments"], cb=sync_cb, q=event_queue, _ctx=ctx):
                                try:
                                    errors = tool.validate_params(params)
                                    if errors:
                                        result = f"[参数错误] {'; '.join(errors)}"
                                    else:
                                        call_params = self.tools._inject_ctx(tool, params, _ctx)
                                        result = await tool.execute_streaming(cb, **call_params)
                                except Exception as e:
                                    import traceback
                                    result = f"[执行错误] {type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}"
                                q.put_nowait(None)  # 哨兵：表示执行完毕
                                return result

                            streaming_task = asyncio.create_task(run_streaming())

                            # 从队列消费事件并 yield 给主流
                            while True:
                                evt = await event_queue.get()
                                if evt is None:
                                    break
                                yield evt  # 透传 subagent_start / subagent_event / subagent_done

                            result = await streaming_task
                        else:
                            # 普通工具：直接执行
                            result = await self.tools.execute(
                                tc["name"], tc["arguments"],
                                session_overrides=session_overrides,
                                session_ctx=ctx,
                            )

                        limit = self._result_limit(tc["name"])
                        if len(result) > limit:
                            result = result[:limit] + f"\n\n...[已截断，原始长度 {len(result)}，工具 {tc['name']} 上限 {limit}]"

                        yield {"type": "tool_result", "id": tc["id"], "name": tc["name"], "content": result}

                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": result,
                        }
                        messages.append(tool_msg)
                        new_messages.append(tool_msg)
                else:
                    if final_content is not None:
                        assistant_msg = {"role": "assistant", "content": final_content}
                        if final_reasoning:
                            assistant_msg["reasoning_content"] = final_reasoning
                        if current_iter_usage:
                            assistant_msg["input_tokens"] = current_iter_usage.get("input_tokens")
                            assistant_msg["output_tokens"] = current_iter_usage.get("output_tokens")
                        new_messages.append(assistant_msg)
                    break
            else:
                final_content = f"已达到最大工具调用次数（{self.max_iterations}），任务可能未完成。"
                yield {"type": "content_delta", "content": final_content}

            # 提前保存，确保 done 事件到达前端后 loadSessions() 能拿到最新 updated_at
            try:
                if new_messages:
                    await self.sessions.save_turn(session_id, user_content, new_messages, images=images, files=files)
                elif user_content:
                    await self.sessions.save_turn(session_id, user_content, [], images=images, files=files)
                _turn_saved = True
            except Exception as _save_err:
                logger.warning(f"save_turn 提前保存失败，将在 finally 重试: {_save_err}")

            yield {
                "type": "done",
                "content": final_content,
                "input_tokens": current_iter_usage.get("input_tokens") if current_iter_usage else None,
                "output_tokens": current_iter_usage.get("output_tokens") if current_iter_usage else None,
            }

            # 主 Agent 才生成标题（后台任务，不阻塞主流程）
            if should_generate_title and final_content:
                logger.info(f"[title-gen] 准备为会话 {session_id} 派发标题生成任务（final_content 长度={len(final_content)}）")
                self._spawn_background(
                    self._generate_title_and_notify(session_id, user_content, final_content, effective_model)
                )
            else:
                logger.info(f"[title-gen] 跳过标题生成 session={session_id} should={should_generate_title} has_final={bool(final_content)}")

        except asyncio.CancelledError:
            logger.info(f"会话 {session_id} 的流式响应被取消")
            if accumulated_content and (not new_messages or new_messages[-1].get("role") != "assistant"):
                new_messages.append({"role": "assistant", "content": accumulated_content})
            raise
        except Exception as e:
            logger.exception(f"Agent 处理出错: {e}")
            from ..utils.errors import classify_error
            classified = classify_error(e)
            yield {
                "type": "error",
                "message": str(e),
                "category": classified.category,
                "retriable": classified.retriable,
                "hint": classified.hint,
            }
        finally:
            # 若提前保存已成功则跳过，否则兜底保存（CancelledError / 异常路径）
            if not _turn_saved:
                if new_messages:
                    await self.sessions.save_turn(session_id, user_content, new_messages, images=images, files=files)
                elif user_content:
                    await self.sessions.save_turn(session_id, user_content, [], images=images, files=files)

            # SubAgent 不做全局记忆整合（throwaway session）
            if not is_subagent:
                self._spawn_background(
                    self.memory.maybe_consolidate(
                        session_id, self.provider, effective_model,
                        context_window=effective_context_window,
                    )
                )

    async def _generate_title_and_notify(
        self, session_id: str, user_message: str, ai_response: str, model: str
    ):
        """后台生成标题并广播 session_title 事件（通过 connection_manager）。"""
        logger.info(f"[title-gen] 开始为会话 {session_id} 生成标题（model={model}）")
        try:
            title = await self._generate_title(user_message, ai_response, model)
            logger.info(f"[title-gen] 会话 {session_id} 生成标题: {title!r}")
            if title:
                ok = await self.sessions.update_title(session_id, title)
                logger.info(f"[title-gen] update_title returned {ok}")
                from ..api.connection_manager import manager
                await manager.broadcast({"type": "session_title", "title": title, "session_id": session_id})
                logger.info(f"[title-gen] broadcast 完成")
            else:
                logger.warning(f"[title-gen] 会话 {session_id} 标题为空，跳过")
        except Exception as e:
            logger.exception(f"[title-gen] 生成会话标题失败: {e}")

    async def _generate_title(self, user_message: str, ai_response: str, model: str) -> str:
        """基于首轮对话内容生成简洁的会话标题。

        注意 max_tokens 要留足给思考型模型（GLM-5.2、DeepSeek-R1 等）的
        reasoning_content —— 那部分不算在最终 content 里但会消耗 output 配额。
        """
        prompt = (
            "为下面这段对话起一个不超过15字的中文标题。"
            "直接输出标题本身，不要引号、标点、前缀说明、思考过程。\n\n"
            f"[用户]\n{user_message[:400]}\n\n"
            f"[助手]\n{ai_response[:400]}\n\n"
            "标题："
        )
        title = ""
        async for event in self.provider.chat_stream(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            model=model,
            temperature=0.3,
            max_tokens=2000,   # 给思考型模型留 reasoning 配额；final content 会自然很短
        ):
            if event.type == "content_delta":
                title += event.content
            elif event.type in ("done", "error"):
                break
        # 清洗：先剥掉 <think>...</think>（部分模型如 DeepSeek-R1 会把思考写到 content 里）
        cleaned = _strip_think_tags(title)
        cleaned = cleaned.strip().strip('"').strip("'").strip("「").strip("」")
        # 只保留第一行（防止模型输出多行）
        cleaned = cleaned.split("\n", 1)[0].strip()
        # 常见前缀清理
        for prefix in ("标题：", "标题:", "Title:", "title:"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        return cleaned[:20]

    @classmethod
    async def create(cls, config, db_manager) -> "AgentLoop":
        """工厂方法：初始化所有组件并返回 AgentLoop 实例。MCP 连接由外部 MCPManager 管理。"""
        from ..providers.litellm_provider import LiteLLMProvider
        from ..tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool, ReadSkillTool
        from ..tools.coding import GlobTool, GrepTool, MultiEditTool, ApplyPatchTool
        from ..tools.shell import (
            ExecTool, SpawnBackgroundTool, ReadProcessOutputTool,
            KillProcessTool, ListProcessesTool,
        )
        from ..tools.web import WebSearchTool, WebFetchTool

        workspace = Path(config.workspace)
        workspace.mkdir(parents=True, exist_ok=True)

        config_dir = Path(config.config_dir).resolve()

        provider = LiteLLMProvider(
            api_key=config.llm.api_key,
            api_base=config.llm.api_base,
        )

        session_manager = SessionManager(db_manager)
        memory_manager = MemoryManager(db_manager, config.llm.context_window_tokens)
        system_skills_dir = Path(config.skills_dir).resolve()
        user_skills_dir = workspace / "skills"
        skills_loader = SkillsLoader(system_skills_dir, user_skills_dir)
        # 启动时将系统 Skills 同步到 workspace/.skills_cache/，保持沙箱内访问
        skills_loader.sync_system_skills(workspace)
        context_builder = ContextBuilder(workspace, config_dir, skills_loader, memory_manager, db_manager)

        tools = ToolRegistry()
        # 文件工具无需 workspace 参数：路径通过 ToolContext.cwd 解析
        tools.register(ReadFileTool())
        tools.register(WriteFileTool())
        tools.register(EditFileTool())
        tools.register(ListDirTool())
        tools.register(ReadSkillTool(workspace))
        # 编码工具集（glob/grep/multi_edit/apply_patch）
        tools.register(GlobTool())
        tools.register(GrepTool())
        tools.register(MultiEditTool())
        tools.register(ApplyPatchTool())
        # ExecTool 保留 default_cwd 兜底（无 ctx 时使用，如老会话）
        tools.register(ExecTool(workspace, config.tools.shell_timeout))
        # 后台进程工具组
        tools.register(SpawnBackgroundTool(workspace))
        tools.register(ReadProcessOutputTool())
        tools.register(KillProcessTool())
        tools.register(ListProcessesTool())
        if config.tools.brave_api_key:
            tools.register(WebSearchTool(config.tools.brave_api_key))
        #tools.register(DuckDuckGoSearchTool())
        tools.register(WebFetchTool())

        loop = cls(
            provider=provider,
            workspace=workspace,
            session_manager=session_manager,
            memory_manager=memory_manager,
            context_builder=context_builder,
            tools=tools,
            model=config.llm.default_model,
            max_iterations=config.llm.max_iterations,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
            confirm_required_tools=set(config.tools.confirm_required_tools),
        )
        return loop


# 避免循环导入
from .skills import SkillsLoader  # noqa: E402
