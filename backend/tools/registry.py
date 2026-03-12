import json
import traceback
from .base import Tool
from loguru import logger


class ToolRegistry:
    """
    工具注册表，支持：
    - 全局禁用（影响所有会话）
    - 会话级覆盖（仅影响单个会话）

    有效状态优先级（高 → 低）：
    1. 会话级 override（True/False）
    2. 全局 disabled 集合
    3. 默认：启用
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._globally_disabled: set[str] = set()

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")

    # ── 全局禁用管理 ────────────────────────────────────────────────────────

    def set_globally_disabled(self, names: set[str]) -> None:
        """批量设置全局禁用集合（用于启动时从 DB 加载）。"""
        self._globally_disabled = set(names)

    def toggle_global(self, name: str) -> bool:
        """切换工具的全局启用状态，返回切换后是否启用。"""
        if name in self._globally_disabled:
            self._globally_disabled.discard(name)
            return True   # 现在启用
        else:
            self._globally_disabled.add(name)
            return False  # 现在禁用

    def is_globally_enabled(self, name: str) -> bool:
        return name not in self._globally_disabled

    def get_globally_disabled(self) -> list[str]:
        return sorted(self._globally_disabled)

    # ── 工具定义 + 状态查询 ─────────────────────────────────────────────────

    def _is_effective_enabled(self, name: str, session_overrides: dict[str, bool] | None) -> bool:
        """计算某工具在给定会话中的有效启用状态。"""
        if session_overrides is not None and name in session_overrides:
            return bool(session_overrides[name])
        return name not in self._globally_disabled

    def get_definitions(self, session_overrides: dict[str, bool] | None = None) -> list[dict]:
        """
        返回当前会话可用的工具 schema 列表。

        :param session_overrides: 会话级 override {"exec": False, "web_search": True}
                                  True=强制启用（即使全局禁用），False=强制禁用
        """
        return [
            t.to_schema()
            for name, t in self._tools.items()
            if self._is_effective_enabled(name, session_overrides)
        ]

    def get_tool_states(self, session_overrides: dict[str, bool] | None = None) -> list[dict]:
        """返回所有工具的可视化状态（用于前端显示）。"""
        result = []
        for name in self._tools:
            global_enabled = name not in self._globally_disabled
            override = (session_overrides or {}).get(name)
            effective = self._is_effective_enabled(name, session_overrides)

            result.append({
                "name": name,
                "global_enabled": global_enabled,
                "session_override": override,  # None / True / False
                "effective_enabled": effective,
                # "global" = 跟随全局, "session_on" = 会话强制启用, "session_off" = 会话强制禁用
                "scope": "global" if override is None
                          else ("session_on" if override else "session_off"),
            })
        return result

    # ── 执行 ────────────────────────────────────────────────────────────────

    async def execute(self, name: str, params: dict,
                      session_overrides: dict[str, bool] | None = None) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"[错误] 工具 '{name}' 不存在"
        # 安全检查：如果运行时该工具已被禁用，拒绝执行
        if not self._is_effective_enabled(name, session_overrides):
            return f"[已禁用] 工具 '{name}' 在当前会话中已被禁用"
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

    def unregister(self, name: str) -> bool:
        """注销指定工具，返回是否成功（工具不存在则返回 False）。"""
        if name in self._tools:
            del self._tools[name]
            self._globally_disabled.discard(name)
            logger.debug(f"注销工具: {name}")
            return True
        return False

    def unregister_by_prefix(self, prefix: str) -> list[str]:
        """注销所有名称以 prefix 开头的工具，返回已注销的工具名列表。"""
        to_remove = [n for n in list(self._tools.keys()) if n.startswith(prefix)]
        for name in to_remove:
            self.unregister(name)
        return to_remove

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
