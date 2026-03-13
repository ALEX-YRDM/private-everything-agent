from abc import ABC, abstractmethod
from typing import Callable
import jsonschema


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """返回 JSON Schema 格式的参数定义。"""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具，返回字符串结果（供 LLM 读取）。"""
        ...

    def to_schema(self) -> dict:
        """转为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def validate_params(self, params: dict) -> list[str]:
        """返回验证错误列表（空表示合法）。"""
        try:
            jsonschema.validate(params, self.parameters)
            return []
        except jsonschema.ValidationError as e:
            return [str(e.message)]


class StreamingTool(Tool, ABC):
    """
    支持在执行期间向调用方流式推送事件的工具基类。

    stream_callback 是一个同步回调 (dict) -> None，
    工具在执行过程中可调用它推送中间事件（如 subagent_start/event/done）。
    AgentLoop 通过 asyncio.Queue 桥接这些事件到主流式输出中。
    """

    @abstractmethod
    async def execute_streaming(
        self,
        stream_callback: Callable[[dict], None],
        **kwargs,
    ) -> str:
        """执行工具（带流式事件推送），返回最终字符串结果。"""
        ...

    async def execute(self, **kwargs) -> str:
        """无 callback 版本（兼容普通工具调用路径）。"""
        return await self.execute_streaming(lambda _: None, **kwargs)
