"""
ConfirmationBroker：破坏性工具执行前请求前端用户确认。

工作流程：
  1. AgentLoop 判定要调用的工具在 confirm_required_tools 列表中，
     且未被会话级信任覆盖。
  2. broker.request(tool_call_id, payload) 通过 stream_callback 推
     一个 tool_confirm 事件到前端，注册一个 Future。
  3. 前端弹卡片给用户选择 allow/deny/trust_path/trust_command，
     通过 tool_confirm_response 事件回传。
  4. WebSocket 层收到回传 → broker.resolve(tool_call_id, decision)
     唤醒 Future，AgentLoop 继续 / 中止。
  5. 超时（默认 300s）视为 deny。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable


DEFAULT_TIMEOUT = 300  # 秒


@dataclass
class ConfirmResponse:
    decision: str  # "allow" | "deny" | "trust_path" | "trust_command"
    extra: str | None = None  # trust_path 用路径、trust_command 用命令前缀


class ConfirmationBroker:
    """每个 WebSocket 连接持有一个 broker 实例。"""

    def __init__(self, stream_callback: Callable[[dict], None], timeout: float = DEFAULT_TIMEOUT):
        self._stream_cb = stream_callback
        self._timeout = timeout
        self._pending: dict[str, asyncio.Future[ConfirmResponse]] = {}

    async def request(self, tool_call_id: str, payload: dict) -> ConfirmResponse:
        """
        向前端发送 tool_confirm 事件并等待响应。

        payload 至少包含：name, args, cwd, why；可选 preview（diff / 命令预览）。
        """
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[ConfirmResponse] = loop.create_future()
        self._pending[tool_call_id] = fut

        self._stream_cb({
            "type": "tool_confirm",
            "id": tool_call_id,
            **payload,
        })

        try:
            return await asyncio.wait_for(fut, timeout=self._timeout)
        except asyncio.TimeoutError:
            return ConfirmResponse(decision="deny", extra="超时未响应")
        finally:
            self._pending.pop(tool_call_id, None)

    def resolve(self, tool_call_id: str, decision: str, extra: str | None = None) -> bool:
        """由 WebSocket 层调用，唤醒等待中的 Future。返回是否找到对应 pending。"""
        fut = self._pending.get(tool_call_id)
        if fut and not fut.done():
            fut.set_result(ConfirmResponse(decision=decision, extra=extra))
            return True
        return False

    def cancel_all(self, reason: str = "会话已断开") -> None:
        """WebSocket 断开时把所有 pending 视为 deny。"""
        for fut in self._pending.values():
            if not fut.done():
                fut.set_result(ConfirmResponse(decision="deny", extra=reason))
        self._pending.clear()
