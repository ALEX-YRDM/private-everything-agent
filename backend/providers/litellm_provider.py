import litellm
import json
from loguru import logger
from .base import LLMProvider, LLMResponse, StreamEvent, ToolCallRequest

litellm.set_verbose = False


class LiteLLMProvider(LLMProvider):
    """
    通过 LiteLLM 统一接入所有主流 LLM。

    支持的模型格式示例：
      - "gpt-4o"                       → OpenAI
      - "claude-3-5-sonnet-20241022"   → Anthropic
      - "deepseek/deepseek-chat"       → DeepSeek
      - "gemini/gemini-2.0-flash"      → Google
      - "ollama/qwen2.5:14b"           → 本地 Ollama
      - "openrouter/anthropic/claude-3.5-sonnet" → OpenRouter
    """

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base

    def _build_kwargs(self, model: str, **kwargs) -> dict:
        kw = {"model": model, **kwargs}
        if self.api_key:
            kw["api_key"] = self.api_key
        if self.api_base:
            kw["api_base"] = self.api_base
        return kw

    async def chat(self, messages, tools=None, model="gpt-4o", **kwargs) -> LLMResponse:
        kw = self._build_kwargs(model, messages=messages, **kwargs)
        if tools:
            kw["tools"] = tools

        response = await litellm.acompletion(**kw)
        return self._parse_response(response)

    async def chat_stream(self, messages, tools=None, model="gpt-4o", **kwargs):
        """
        流式生成 StreamEvent。
        当有工具调用时，LiteLLM 在 finish_reason=tool_calls 时一次性返回完整工具调用。
        """
        kw = self._build_kwargs(model, messages=messages, stream=True, **kwargs)
        if tools:
            kw["tools"] = tools

        accumulated_tool_calls: dict[int, dict] = {}
        accumulated_content = ""

        async for chunk in await litellm.acompletion(**kw):
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if delta.content:
                accumulated_content += delta.content
                yield StreamEvent(type="content_delta", content=delta.content)

            # 思维链（DeepSeek R1 等）
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield StreamEvent(type="thinking", content=reasoning)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        accumulated_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        accumulated_tool_calls[idx]["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        accumulated_tool_calls[idx]["arguments"] += tc_delta.function.arguments

            if finish_reason == "tool_calls":
                tool_calls = []
                for tc in accumulated_tool_calls.values():
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(
                        ToolCallRequest(id=tc["id"], name=tc["name"], arguments=args)
                    )
                    yield StreamEvent(
                        type="tool_call",
                        data={"id": tc["id"], "name": tc["name"], "args": args},
                    )
                yield StreamEvent(
                    type="tool_calls_ready",
                    data={
                        "content": accumulated_content,
                        "tool_calls": [
                            {"id": t.id, "name": t.name, "arguments": t.arguments}
                            for t in tool_calls
                        ],
                    },
                )
            elif finish_reason == "stop":
                yield StreamEvent(type="done", content=accumulated_content)

    def _parse_response(self, response) -> LLMResponse:
        msg = response.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, AttributeError):
                    args = {}
                tool_calls.append(
                    ToolCallRequest(id=tc.id, name=tc.function.name, arguments=args)
                )
        reasoning = getattr(msg, "reasoning_content", None)
        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
            reasoning_content=reasoning,
        )
