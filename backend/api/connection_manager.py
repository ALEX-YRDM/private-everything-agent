"""
全局 WebSocket 连接管理器。

支持：
- 跟踪所有活跃连接
- 向所有连接广播系统事件（定时任务通知等）
"""
from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.debug(f"WebSocket 连接建立，当前连接数: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
            logger.debug(f"WebSocket 连接断开，当前连接数: {len(self._connections)}")

    async def broadcast(self, data: dict):
        """向所有活跃连接广播消息（自动清理失效连接）。"""
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


# 全局单例，供 scheduler 和 websocket 路由共享
manager = ConnectionManager()
