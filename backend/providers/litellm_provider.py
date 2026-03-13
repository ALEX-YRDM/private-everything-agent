import litellm
import json
from loguru import logger
from .base import LLMProvider, LLMResponse, StreamEvent, ToolCallRequest

litellm.set_verbose = False

# LiteLLM 原生支持的 provider（有内置路由，无需特殊处理）
_NATIVE_PROVIDERS = frozenset({
    # 主流商业
    "openai", "anthropic", "gemini", "deepseek", "groq", "mistral",
    "together_ai", "openrouter", "xai", "perplexity", "cohere",
    # 云厂商
    "azure", "bedrock", "vertex_ai",
    # 国内
    "volcengine", "moonshot", "zhipuai", "zai", "baidu", "dashscope",
    "minimax", "qianfan", "spark", "hunyuan",
    # 本地/开源
    "ollama", "palm", "replicate", "huggingface",
    # 其他已知
    "ai21", "nlp_cloud", "aleph_alpha", "petals", "anyscale", "voyage",
    "openllm", "oobabooga",
})


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
        from .key_manager import get_provider_credentials, extract_provider
        kw = {"model": model, **kwargs}

        # 从注册表查询该模型 provider 的 key/base（覆盖实例级全局配置）
        creds = get_provider_credentials(model)
        api_key  = creds.get("api_key")  or self.api_key
        api_base = creds.get("api_base") or self.api_base

        if api_key:
            kw["api_key"] = api_key
        if api_base:
            kw["api_base"] = api_base

        # 自定义（非原生）Provider 且配置了 api_base：
        # LiteLLM 不认识该 provider 前缀，将 model 重写为 openai/<model_name>
        # 以强制走 OpenAI 兼容路由（适用于 LM Studio、vLLM、OneAPI 等自定义端点）
        provider = extract_provider(model)
        if api_base and provider not in _NATIVE_PROVIDERS:
            model_name = model.split("/", 1)[1] if "/" in model else model
            kw["model"] = f"openai/{model_name}"

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
        accumulated_reasoning = ""

        async for chunk in await litellm.acompletion(**kw):
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if delta.content:
                accumulated_content += delta.content
                yield StreamEvent(type="content_delta", content=delta.content)

            # 思维链（DeepSeek R1 等）—— 同时累积，以便写回 assistant 消息
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                accumulated_reasoning += reasoning
                yield StreamEvent(type="thinking", content=reasoning)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {"id": "", "name": "", "arguments": "", "_emitted": False}
                    if tc_delta.id:
                        accumulated_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        accumulated_tool_calls[idx]["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        accumulated_tool_calls[idx]["arguments"] += tc_delta.function.arguments

                    tc_acc = accumulated_tool_calls[idx]

                    # 一旦 id 和 name 就绪就立即推送 tool_call，让前端实时显示工具调用
                    if not tc_acc["_emitted"] and tc_acc["id"] and tc_acc["name"]:
                        tc_acc["_emitted"] = True
                        yield StreamEvent(
                            type="tool_call",
                            data={"id": tc_acc["id"], "name": tc_acc["name"], "args": {}},
                        )

                    # 参数增量实时推送，让前端逐字显示正在生成的参数内容
                    if tc_delta.function and tc_delta.function.arguments and tc_acc["id"]:
                        yield StreamEvent(
                            type="tool_call_delta",
                            data={"id": tc_acc["id"], "args_delta": tc_delta.function.arguments},
                        )

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
                # tool_call 事件已在流式过程中提前发出，这里只需发 tool_calls_ready
                yield StreamEvent(
                    type="tool_calls_ready",
                    data={
                        "content": accumulated_content,
                        # reasoning_content 需原样回传给 DeepSeek 等 reasoning 模型
                        "reasoning_content": accumulated_reasoning or None,
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
