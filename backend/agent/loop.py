import asyncio
import json
from pathlib import Path
from loguru import logger

from ..providers.base import LLMProvider, StreamEvent
from ..tools.registry import ToolRegistry
from ..session.manager import SessionManager
from .context import ContextBuilder
from .memory import MemoryManager


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

    TOOL_RESULT_MAX_CHARS = 8000

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
        # SubAgent 相关
        self.depth = depth                    # 0=主Agent，1+=SubAgent
        self.allowed_tools = allowed_tools    # 工具白名单（SubAgent 动态指定）
        self._current_session_id: str | None = None  # 当前处理的 session_id（供 SpawnSubAgentsTool 读取）

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
        )

    async def process_stream(self, session_id: str, user_content: str, model: str | None = None, images: list[str] | None = None):
        """
        处理用户消息，以异步生成器方式 yield 事件字典。

        事件类型（主 Agent）：
        - {"type": "thinking", "content": "..."}          LLM 推理过程
        - {"type": "tool_call", "name": "...", "args": {...}}   工具调用
        - {"type": "tool_result", "name": "...", "content": "..."} 工具结果
        - {"type": "subagent_start", "subagent_id": "...", "session_id": "...", "task": "..."}
        - {"type": "subagent_event", "subagent_id": "...", "event": {...}}
        - {"type": "subagent_done", "subagent_id": "...", "result": "..."}
        - {"type": "content_delta", "content": "..."}     流式 token
        - {"type": "done", "content": "..."}              完成
        - {"type": "error", "message": "..."}             出错
        """
        self._current_session_id = session_id

        is_subagent = self.depth > 0

        if is_subagent:
            # SubAgent：简洁上下文，无历史，无记忆
            messages = await self.context.build_subagent_messages(user_content)
            session_overrides: dict[str, bool] = {}
            effective_model = model or self.model
            should_generate_title = False
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
            effective_model = model or session_model or self.model
            messages = await self.context.build_messages(history, user_content, session_id, images=images)

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
                        break

                    elif event.type == "error":
                        yield {"type": "error", "message": event.content or "未知错误"}
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

                            async def run_streaming(tool=tool_obj, params=tc["arguments"], cb=sync_cb, q=event_queue):
                                try:
                                    errors = tool.validate_params(params)
                                    if errors:
                                        result = f"[参数错误] {'; '.join(errors)}"
                                    else:
                                        result = await tool.execute_streaming(cb, **params)
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
                                tc["name"], tc["arguments"], session_overrides=session_overrides
                            )

                        if len(result) > self.TOOL_RESULT_MAX_CHARS:
                            result = result[: self.TOOL_RESULT_MAX_CHARS] + "...[已截断]"

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
                    await self.sessions.save_turn(session_id, user_content, new_messages, images=images)
                elif user_content:
                    await self.sessions.save_turn(session_id, user_content, [], images=images)
                _turn_saved = True
            except Exception as _save_err:
                logger.warning(f"save_turn 提前保存失败，将在 finally 重试: {_save_err}")

            yield {"type": "done", "content": final_content}

            # 主 Agent 才生成标题（后台任务，不阻塞主流程）
            if should_generate_title and final_content:
                asyncio.create_task(
                    self._generate_title_and_notify(session_id, user_content, final_content, effective_model)
                )

        except asyncio.CancelledError:
            logger.info(f"会话 {session_id} 的流式响应被取消")
            if accumulated_content and (not new_messages or new_messages[-1].get("role") != "assistant"):
                new_messages.append({"role": "assistant", "content": accumulated_content})
            raise
        except Exception as e:
            logger.exception(f"Agent 处理出错: {e}")
            yield {"type": "error", "message": str(e)}
        finally:
            # 若提前保存已成功则跳过，否则兜底保存（CancelledError / 异常路径）
            if not _turn_saved:
                if new_messages:
                    await self.sessions.save_turn(session_id, user_content, new_messages, images=images)
                elif user_content:
                    await self.sessions.save_turn(session_id, user_content, [], images=images)

            # SubAgent 不做全局记忆整合（throwaway session）
            if not is_subagent:
                asyncio.create_task(
                    self.memory.maybe_consolidate(
                        session_id, self.provider, effective_model,
                        context_window=effective_context_window,
                    )
                )

    async def _generate_title_and_notify(
        self, session_id: str, user_message: str, ai_response: str, model: str
    ):
        """后台生成标题并广播 session_title 事件（通过 connection_manager）。"""
        try:
            title = await self._generate_title(user_message, ai_response, model)
            if title:
                await self.sessions.update_title(session_id, title)
                from ..api.connection_manager import manager
                await manager.broadcast({"type": "session_title", "title": title, "session_id": session_id})
        except Exception as e:
            logger.warning(f"生成会话标题失败: {e}")

    async def _generate_title(self, user_message: str, ai_response: str, model: str) -> str:
        """基于首轮对话内容生成简洁的会话标题。"""
        prompt = (
            "根据以下对话，生成一个简洁的中文标题（不超过15个字，只输出标题本身，不要引号或标点）：\n\n"
            f"用户：{user_message[:300]}\n"
            f"助手：{ai_response[:300]}\n\n"
            "标题："
        )
        title = ""
        async for event in self.provider.chat_stream(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            model=model,
            temperature=0.3,
            max_tokens=30,
        ):
            if event.type == "content_delta":
                title += event.content
            elif event.type in ("done", "error"):
                break
        return title.strip().strip('"').strip("'")[:20]

    @classmethod
    async def create(cls, config, db_manager) -> "AgentLoop":
        """工厂方法：初始化所有组件并返回 AgentLoop 实例。MCP 连接由外部 MCPManager 管理。"""
        from ..providers.litellm_provider import LiteLLMProvider
        from ..tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool, ReadSkillTool
        from ..tools.shell import ExecTool
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
        tools.register(ReadFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(WriteFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(EditFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(ListDirTool(workspace, config.tools.restrict_to_workspace))
        tools.register(ReadSkillTool(workspace))
        tools.register(ExecTool(workspace, config.tools.shell_timeout))
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
        )
        return loop


# 避免循环导入
from .skills import SkillsLoader  # noqa: E402
