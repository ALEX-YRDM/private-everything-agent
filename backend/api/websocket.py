import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from .connection_manager import manager

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket 协议：

    客户端 → 服务端：
    {"type": "message", "content": "用户消息"}
    {"type": "stop"}                             # 中断当前任务

    服务端 → 客户端（会话级）：
    {"type": "thinking", "content": "..."}       # LLM 推理过程
    {"type": "tool_call", "name": "...", "args": {...}}
    {"type": "tool_result", "name": "...", "content": "..."}
    {"type": "content_delta", "content": "..."}  # 流式 token
    {"type": "done", "content": "..."}           # 完成
    {"type": "error", "message": "..."}          # 错误

    服务端 → 客户端（全局广播）：
    {"type": "task_notification", "task_id": ..., "task_name": "...",
     "status": "success"|"error", "session_id": "...", "message": "..."}
    """
    await manager.connect(websocket)
    agent = websocket.app.state.agent
    current_task: asyncio.Task | None = None

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "stop":
                if current_task and not current_task.done():
                    current_task.cancel()
                    logger.info(f"会话 {session_id} 任务已停止")
                continue

            if data.get("type") == "message":
                if current_task and not current_task.done():
                    current_task.cancel()

                async def stream_response(content: str):
                    try:
                        async for event in agent.process_stream(
                            session_id=session_id,
                            user_content=content,
                        ):
                            await websocket.send_json(event)
                    except asyncio.CancelledError:
                        try:
                            await websocket.send_json({"type": "done", "content": ""})
                        except Exception:
                            pass
                    except Exception as e:
                        logger.exception(f"流式响应出错: {e}")
                        try:
                            await websocket.send_json({"type": "error", "message": str(e)})
                        except Exception:
                            pass

                current_task = asyncio.create_task(stream_response(data["content"]))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"会话 {session_id} WebSocket 断开")
        if current_task:
            current_task.cancel()
    except Exception as e:
        manager.disconnect(websocket)
        logger.exception(f"WebSocket 处理出错: {e}")
        if current_task:
            current_task.cancel()
