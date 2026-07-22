"""
MengdieClient：TUI 与已有 FastAPI backend 之间的 HTTP + WebSocket 客户端。

- 与 web 前端共用同一套 REST 和 /ws/{session_id} 协议。
- 面向 TUI 简化：暴露异步 API，事件通过回调注入 Textual 应用。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

import httpx
import websockets


StreamEvent = dict[str, Any]
EventCallback = Callable[[StreamEvent], Awaitable[None] | None]


class MengdieClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        # 会话切换/重连要复用连接池
        self.http = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._ws_recv_task: asyncio.Task | None = None
        self._on_event: EventCallback | None = None
        self._on_close: Callable[[], None] | None = None

    # ── 生命周期 ─────────────────────────────────────────

    async def close(self) -> None:
        await self.disconnect_ws()
        await self.http.aclose()

    # ── HTTP 探测 ──────────────────────────────────────

    async def ping(self) -> bool:
        """后端是否已启动。用 /api/config（轻量）探测。"""
        try:
            r = await self.http.get("/api/config", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    # ── 会话管理 ────────────────────────────────────────

    async def list_sessions(self) -> list[dict]:
        r = await self.http.get("/api/sessions")
        r.raise_for_status()
        return r.json().get("sessions", [])

    async def create_session(self, title: str = "新会话",
                             working_dir: str | None = None) -> dict:
        payload: dict = {"title": title}
        if working_dir is not None:
            payload["working_dir"] = working_dir
        r = await self.http.post("/api/sessions", json=payload)
        r.raise_for_status()
        return r.json()

    async def get_messages(self, session_id: str) -> list[dict]:
        r = await self.http.get(f"/api/sessions/{session_id}/messages")
        r.raise_for_status()
        return r.json().get("messages", [])

    async def delete_session(self, session_id: str) -> None:
        r = await self.http.delete(f"/api/sessions/{session_id}")
        r.raise_for_status()

    async def rename_session(self, session_id: str, title: str) -> None:
        r = await self.http.put(f"/api/sessions/{session_id}/title", json={"title": title})
        r.raise_for_status()

    # ── 模型 / 配置 ─────────────────────────────────────

    async def get_config(self) -> dict:
        r = await self.http.get("/api/config")
        r.raise_for_status()
        return r.json()

    # ── 文件树 / 文件搜索 ──────────────────────────────

    async def list_files(self, session_id: str, path: str = "",
                         depth: int = 1) -> dict:
        r = await self.http.get(
            f"/api/sessions/{session_id}/files",
            params={"path": path, "depth": depth},
        )
        r.raise_for_status()
        return r.json()

    async def get_file_content(self, session_id: str, path: str) -> dict:
        r = await self.http.get(
            f"/api/sessions/{session_id}/file-content",
            params={"path": path},
        )
        r.raise_for_status()
        return r.json()

    async def search_files(self, session_id: str, q: str,
                           limit: int = 30) -> list[dict]:
        r = await self.http.get(
            f"/api/sessions/{session_id}/files/search",
            params={"q": q, "limit": limit},
        )
        r.raise_for_status()
        return r.json().get("results", [])

    # ── Plan Mode ──────────────────────────────────────

    async def get_plan_mode(self, session_id: str) -> bool:
        r = await self.http.get(f"/api/sessions/{session_id}/plan-mode")
        r.raise_for_status()
        return bool(r.json().get("plan_mode"))

    async def set_plan_mode(self, session_id: str, enable: bool) -> None:
        r = await self.http.put(
            f"/api/sessions/{session_id}/plan-mode",
            json={"plan_mode": enable},
        )
        r.raise_for_status()

    # ── Todos ──────────────────────────────────────────

    async def get_todos(self, session_id: str) -> list[dict]:
        r = await self.http.get(f"/api/sessions/{session_id}/todos")
        r.raise_for_status()
        return r.json().get("todos", []) or []

    # ── Skills ─────────────────────────────────────────

    async def list_skills(self) -> list[dict]:
        r = await self.http.get("/api/skills")
        r.raise_for_status()
        return r.json().get("skills", [])

    async def get_skill(self, name: str) -> dict:
        r = await self.http.get(f"/api/skills/{name}")
        r.raise_for_status()
        return r.json()

    # ── MCP ────────────────────────────────────────────

    async def list_mcp_servers(self) -> list[dict]:
        r = await self.http.get("/api/mcp-servers")
        r.raise_for_status()
        # 返回结构：{ servers: [...] } 或直接 list —— 兼容处理
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("servers") or data.get("data") or []

    async def reconnect_mcp(self, server_id: int) -> None:
        r = await self.http.post(f"/api/mcp-servers/{server_id}/reconnect")
        r.raise_for_status()

    async def toggle_mcp(self, server_id: int) -> None:
        r = await self.http.post(f"/api/mcp-servers/{server_id}/toggle")
        r.raise_for_status()

    # ── 模型 ───────────────────────────────────────────

    async def list_models(self) -> list[dict]:
        r = await self.http.get("/api/models")
        r.raise_for_status()
        data = r.json()
        return data.get("models") if isinstance(data, dict) else data

    async def switch_model(self, model_id: str) -> None:
        r = await self.http.post("/api/models/switch", json={"model_id": model_id})
        r.raise_for_status()

    # ── WebSocket ──────────────────────────────────────

    @property
    def ws_url(self) -> str:
        # http → ws, https → wss
        return self.base_url.replace("http", "ws", 1) + "/ws"

    def is_ws_connected(self) -> bool:
        return self._ws is not None and self._ws.state.name == "OPEN"

    async def connect_ws(self, session_id: str,
                         on_event: EventCallback,
                         on_close: Callable[[], None] | None = None) -> None:
        """连接指定 session 的 WS 通道；开始后台 recv loop。"""
        await self.disconnect_ws()

        self._on_event = on_event
        self._on_close = on_close

        self._ws = await websockets.connect(
            f"{self.ws_url}/{session_id}",
            open_timeout=5.0,
            close_timeout=2.0,
            max_size=None,  # 允许大消息（tool_result 之类）
        )
        self._ws_recv_task = asyncio.create_task(self._recv_loop())

    async def disconnect_ws(self) -> None:
        if self._ws_recv_task:
            self._ws_recv_task.cancel()
            self._ws_recv_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if self._on_event is None:
                    continue
                # 单条事件 raise 不能打断 recv loop，否则后续 done 事件会丢
                try:
                    result = self._on_event(evt)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    import traceback
                    from loguru import logger
                    logger.exception(
                        f"TUI on_event 抛错，事件被吞：type={evt.get('type')}"
                    )
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        except Exception:
            from loguru import logger
            logger.exception("TUI WS recv loop 意外崩溃")
        finally:
            if self._on_close is not None:
                try:
                    self._on_close()
                except Exception:
                    pass

    async def send_message(self, content: str,
                           images: list[str] | None = None,
                           files: list[dict] | None = None) -> None:
        if self._ws is None:
            raise RuntimeError("WS 未连接")
        payload: dict = {"type": "message", "content": content}
        if images:
            payload["images"] = images
        if files:
            payload["files"] = files
        await self._ws.send(json.dumps(payload))

    async def send_stop(self) -> None:
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "stop"}))

    async def send_confirm(self, tc_id: str, decision: str,
                           extra: str | None = None) -> None:
        if self._ws is None:
            raise RuntimeError("WS 未连接")
        payload: dict = {
            "type": "tool_confirm_response",
            "id": tc_id,
            "decision": decision,
        }
        if extra is not None:
            payload["extra"] = extra
        await self._ws.send(json.dumps(payload))
