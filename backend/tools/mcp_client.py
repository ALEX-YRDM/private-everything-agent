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


class MCPManager:
    """
    管理所有 MCP 服务器连接的生命周期，支持运行时热插拔。

    每个服务器独立持有一个 AsyncExitStack，connect/disconnect 互不影响。
    工具按 mcp_{server_name}_{tool_name} 命名，断开时按前缀批量注销。
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        # name -> AsyncExitStack
        self._stacks: dict[str, AsyncExitStack] = {}
        # name -> {status, error_msg, tools_count}
        self._status: dict[str, dict] = {}

    # ── 连接 / 断开 ─────────────────────────────────────────────────────────

    async def connect(self, server: dict) -> bool:
        """
        连接单个 MCP 服务器，将其工具注册到 ToolRegistry。
        若已连接则先断开再重连。返回是否成功。

        server 字典字段：name, transport, command(list), url, env(dict), enabled
        """
        if not MCP_AVAILABLE:
            self._set_status(server["name"], "error", "mcp 包未安装", 0)
            return False

        name = server["name"]
        if name in self._stacks:
            await self.disconnect(name)

        stack = AsyncExitStack()
        try:
            transport = server.get("transport", "stdio")

            if transport == "stdio":
                # 标准 MCP 格式：command（可执行文件）+ args（参数列表）
                cmd: str = server.get("command") or ""
                if not cmd:
                    raise ValueError("stdio transport 需要填写 command（可执行文件路径，如 npx）")
                args: list = server.get("args") or []
                env: dict | None = server.get("env") or None
                params = StdioServerParameters(
                    command=cmd,
                    args=args,
                    env=env if env else None,
                )
                read, write = await stack.enter_async_context(stdio_client(params))

            elif transport == "sse":
                url = server.get("url")
                if not url:
                    raise ValueError("sse transport 需要填写 url")
                read, write = await stack.enter_async_context(sse_client(url))

            else:
                raise ValueError(f"不支持的 transport 类型: {transport}")

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools_response = await session.list_tools()
            count = 0
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
                self.registry.register(wrapper)
                count += 1

            self._stacks[name] = stack
            self._set_status(name, "connected", None, count)
            logger.info(f"MCP 服务器 '{name}' 连接成功，注册了 {count} 个工具")
            return True

        except Exception as e:
            await stack.aclose()
            self._set_status(name, "error", str(e), 0)
            logger.warning(f"连接 MCP 服务器 '{name}' 失败: {e}")
            return False

    async def disconnect(self, name: str) -> None:
        """断开指定服务器，注销其所有工具。"""
        # 注销工具
        prefix = f"mcp_{name}_"
        removed = self.registry.unregister_by_prefix(prefix)
        if removed:
            logger.debug(f"MCP '{name}' 注销工具: {removed}")

        # 关闭连接
        if name in self._stacks:
            try:
                await self._stacks[name].aclose()
            except Exception as e:
                logger.warning(f"关闭 MCP '{name}' 连接时出错: {e}")
            del self._stacks[name]

        self._set_status(name, "disconnected", None, 0)
        logger.info(f"MCP 服务器 '{name}' 已断开")

    async def reconnect(self, server: dict) -> bool:
        """断开后重新连接。"""
        await self.disconnect(server["name"])
        return await self.connect(server)

    async def close_all(self) -> None:
        """关闭所有连接（应用退出时调用）。"""
        for name in list(self._stacks.keys()):
            await self.disconnect(name)

    # ── 状态查询 ────────────────────────────────────────────────────────────

    def get_status(self, name: str) -> dict:
        return self._status.get(name, {"status": "disconnected", "error_msg": None, "tools_count": 0})

    def get_all_status(self) -> dict[str, dict]:
        return dict(self._status)

    def is_connected(self, name: str) -> bool:
        return self._status.get(name, {}).get("status") == "connected"

    # ── 内部工具 ────────────────────────────────────────────────────────────

    def _set_status(self, name: str, status: str, error_msg: str | None, tools_count: int):
        self._status[name] = {
            "status": status,
            "error_msg": error_msg,
            "tools_count": tools_count,
        }
