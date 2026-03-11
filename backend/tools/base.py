from abc import ABC, abstractmethod
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
