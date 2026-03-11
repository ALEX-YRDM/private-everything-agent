from contextlib import AsyncExitStack
from loguru import logger

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("mcp 包未安装，MCP 功能不可用")

from .base import Tool
from .registry import ToolRegistry


class MCPToolWrapper(Tool):
    """将单个 MCP 工具包装为标准 Tool 接口。"""

    def __init__(self, server_name: str, tool_def: dict, session):
        self._name = f"mcp_{server_name}_{tool_def['name']}"
        self._description = f"[{server_name}] {tool_def.get('description', '')}"
        self._parameters = tool_def.get("inputSchema", {"type": "object", "properties": {}})
        self._session = session
        self._original_name = tool_def["name"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return self._parameters

    async def execute(self, **kwargs) -> str:
        result = await self._session.call_tool(self._original_name, kwargs)
        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
        return "\n".join(parts) or "(无输出)"


async def connect_mcp_servers(
    servers: list[dict],
    registry: ToolRegistry,
    exit_stack: AsyncExitStack,
) -> None:
    """
    连接所有 MCP 服务器，将其工具注册到 ToolRegistry。
    exit_stack 管理生命周期，在应用关闭时统一清理。
    """
    if not MCP_AVAILABLE:
        logger.error("mcp 包未安装，跳过 MCP 服务器连接")
        return

    for server in servers:
        name = server["name"]
        transport = server.get("transport", "stdio")

        try:
            if transport == "stdio":
                params = StdioServerParameters(
                    command=server["command"][0],
                    args=server["command"][1:],
                    env=server.get("env"),
                )
                read, write = await exit_stack.enter_async_context(stdio_client(params))
            elif transport == "sse":
                read, write = await exit_stack.enter_async_context(sse_client(server["url"]))
            else:
                raise ValueError(f"不支持的 MCP transport: {transport}")

            session = await exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools_response = await session.list_tools()
            for tool_def in tools_response.tools:
                wrapper = MCPToolWrapper(
                    server_name=name,
                    tool_def={
                        "name": tool_def.name,
                        "description": tool_def.description,
                        "inputSchema": (
                            tool_def.inputSchema.model_dump()
                            if hasattr(tool_def.inputSchema, "model_dump")
                            else dict(tool_def.inputSchema)
                        ),
                    },
                    session=session,
                )
                registry.register(wrapper)
            logger.info(f"MCP 服务器 '{name}' 连接成功，注册了 {len(tools_response.tools)} 个工具")

        except Exception as e:
            logger.warning(f"连接 MCP 服务器 '{name}' 失败: {e}")
