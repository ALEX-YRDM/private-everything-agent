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

    async def process_stream(self, session_id: str, user_content: str, model: str | None = None):
        """
        处理用户消息，以异步生成器方式 yield 事件字典。

        事件类型：
        - {"type": "thinking", "content": "..."}          LLM 推理过程
        - {"type": "tool_call", "name": "...", "args": {...}}   工具调用
        - {"type": "tool_result", "name": "...", "content": "..."} 工具结果
        - {"type": "content_delta", "content": "..."}     流式 token
        - {"type": "done", "content": "..."}              完成
        - {"type": "error", "message": "..."}             出错
        """
        history = await self.sessions.get_history(session_id)
        messages = await self.context.build_messages(history, user_content, session_id)

        # 获取会话级工具覆盖配置 + 会话专属模型
        session_row = await self.sessions.get_session(session_id)
        session_model = (session_row or {}).get("model") or None
        session_meta = await self.memory.db.get_session_metadata(session_id)
        session_overrides: dict[str, bool] = session_meta.get("tool_overrides", {})

        tool_defs = self.tools.get_definitions(session_overrides=session_overrides)

        # 优先级：显式 model 参数（定时任务覆盖）> 会话专属模型 > 全局默认模型
        effective_model = model or session_model or self.model

        new_messages: list[dict] = []
        final_content: str | None = None

        try:
            for iteration in range(self.max_iterations):
                accumulated_content = ""
                tool_calls_ready = None

                async for event in self.provider.chat_stream(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                    model=effective_model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                ):
                    if event.type == "content_delta":
                        accumulated_content += event.content
                        yield {"type": "content_delta", "content": event.content}

                    elif event.type == "thinking":
                        yield {"type": "thinking", "content": event.content}

                    elif event.type == "tool_call":
                        yield {"type": "tool_call", **event.data}

                    elif event.type == "tool_calls_ready":
                        tool_calls_ready = event.data

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
                    # DeepSeek reasoning 模型要求 tool_calls 消息里必须携带 reasoning_content
                    if tc_reasoning:
                        assistant_msg["reasoning_content"] = tc_reasoning
                    messages.append(assistant_msg)
                    new_messages.append(assistant_msg)

                    for tc in tc_list:
                        result = await self.tools.execute(
                            tc["name"], tc["arguments"], session_overrides=session_overrides
                        )
                        if len(result) > self.TOOL_RESULT_MAX_CHARS:
                            result = result[: self.TOOL_RESULT_MAX_CHARS] + "...[已截断]"

                        yield {"type": "tool_result", "name": tc["name"], "content": result}

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
                        new_messages.append(assistant_msg)
                    break
            else:
                final_content = f"已达到最大工具调用次数（{self.max_iterations}），任务可能未完成。"
                yield {"type": "content_delta", "content": final_content}

            yield {"type": "done", "content": final_content}

        except asyncio.CancelledError:
            logger.info(f"会话 {session_id} 的流式响应被取消")
            raise
        except Exception as e:
            logger.exception(f"Agent 处理出错: {e}")
            yield {"type": "error", "message": str(e)}
        finally:
            if new_messages:
                user_content_clean = self.context.strip_runtime_context(user_content)
                await self.sessions.save_turn(session_id, user_content_clean, new_messages)

            asyncio.create_task(
                self.memory.maybe_consolidate(
                    session_id, messages, self.provider, self.model
                )
            )

    @classmethod
    async def create(cls, config, db_manager) -> "AgentLoop":
        """工厂方法：初始化所有组件并返回 AgentLoop 实例。MCP 连接由外部 MCPManager 管理。"""
        from ..providers.litellm_provider import LiteLLMProvider
        from ..tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
        from ..tools.shell import ExecTool
        from ..tools.web import WebSearchTool, DuckDuckGoSearchTool, WebFetchTool

        workspace = Path(config.workspace)
        workspace.mkdir(parents=True, exist_ok=True)

        provider = LiteLLMProvider(
            api_key=config.llm.api_key,
            api_base=config.llm.api_base,
        )

        session_manager = SessionManager(db_manager)
        memory_manager = MemoryManager(db_manager, config.llm.context_window_tokens)
        skills_loader = SkillsLoader(Path(config.skills_dir))
        context_builder = ContextBuilder(workspace, skills_loader, memory_manager)

        tools = ToolRegistry()
        tools.register(ReadFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(WriteFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(EditFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(ListDirTool(workspace, config.tools.restrict_to_workspace))
        tools.register(ExecTool(workspace, config.tools.shell_timeout))
        if config.tools.brave_api_key:
            tools.register(WebSearchTool(config.tools.brave_api_key))
        tools.register(DuckDuckGoSearchTool())
        tools.register(WebFetchTool())

        return cls(
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


# 避免循环导入
from .skills import SkillsLoader  # noqa: E402
