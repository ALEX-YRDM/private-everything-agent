from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import asyncio


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    reasoning_content: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class StreamEvent:
    type: str  # "thinking" / "content_delta" / "tool_call" / "tool_calls_ready" / "tool_result" / "done" / "error"
    content: str | None = None
    data: dict | None = None


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict] | None = None, **kwargs) -> LLMResponse:
        """非流式调用，返回完整响应。"""
        ...

    @abstractmethod
    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None, **kwargs):
        """流式调用，异步生成器，yield StreamEvent。"""
        ...

    async def chat_with_retry(self, messages, tools=None, max_retries=3, **kwargs) -> LLMResponse:
        """带指数退避重试（应对 429/503）。"""
        for attempt in range(max_retries):
            try:
                return await self.chat(messages, tools, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if any(code in str(e) for code in ["429", "503", "rate_limit", "overloaded"]):
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
