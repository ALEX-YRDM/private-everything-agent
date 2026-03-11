import traceback
from .base import Tool
from loguru import logger


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")

    def get_definitions(self) -> list[dict]:
        """返回所有工具的 function calling schema。"""
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"[错误] 工具 '{name}' 不存在"
        errors = tool.validate_params(params)
        if errors:
            return f"[参数错误] {'; '.join(errors)}"
        try:
            result = await tool.execute(**params)
            if len(result) > 10000:
                result = result[:10000] + f"\n...[结果已截断，共 {len(result)} 字符]"
            return result
        except Exception as e:
            return f"[执行错误] {type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}"

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
