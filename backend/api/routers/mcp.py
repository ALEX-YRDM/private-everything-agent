from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..deps import get_db, get_mcp_manager

router = APIRouter(prefix="/mcp-servers", tags=["mcp"])


class MCPServerCreate(BaseModel):
    name: str
    display_name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = []
    url: str | None = None
    env: dict[str, str] = {}
    headers: dict[str, str] = {}
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    display_name: str | None = None
    transport: str | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    enabled: bool | None = None


def _with_status(server: dict, mcp_manager) -> dict:
    if mcp_manager:
        status = mcp_manager.get_status(server["name"])
    else:
        status = {"status": "disconnected", "error_msg": None, "tools_count": 0}
    return {**server, **status}


@router.get("")
async def list_mcp_servers(db=Depends(get_db), mcp_manager=Depends(get_mcp_manager)):
    servers = await db.list_mcp_servers()
    return {"servers": [_with_status(s, mcp_manager) for s in servers]}


@router.post("")
async def create_mcp_server(body: MCPServerCreate, db=Depends(get_db), mcp_manager=Depends(get_mcp_manager)):
    server = await db.create_mcp_server(
        name=body.name, display_name=body.display_name, transport=body.transport,
        command=body.command, args=body.args, url=body.url, env=body.env,
        headers=body.headers, enabled=body.enabled,
    )
    if body.enabled and mcp_manager:
        await mcp_manager.connect(server)
    return _with_status(server, mcp_manager)


@router.put("/{server_id}")
async def update_mcp_server(server_id: int, body: MCPServerUpdate,
                            db=Depends(get_db), mcp_manager=Depends(get_mcp_manager)):
    updates = body.model_dump(exclude_none=True)
    server = await db.update_mcp_server(server_id, **updates)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    if mcp_manager:
        if server.get("enabled"):
            await mcp_manager.reconnect(server)
        else:
            await mcp_manager.disconnect(server["name"])
    return _with_status(server, mcp_manager)


@router.delete("/{server_id}")
async def delete_mcp_server(server_id: int, db=Depends(get_db), mcp_manager=Depends(get_mcp_manager)):
    server = await db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    if mcp_manager:
        await mcp_manager.disconnect(server["name"])
    ok = await db.delete_mcp_server(server_id)
    if not ok:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    return {"ok": True}


@router.post("/{server_id}/reconnect")
async def reconnect_mcp_server(server_id: int, db=Depends(get_db), mcp_manager=Depends(get_mcp_manager)):
    server = await db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    if not mcp_manager:
        raise HTTPException(status_code=503, detail="MCP 管理器未初始化")
    success = await mcp_manager.reconnect(server)
    return _with_status(server, mcp_manager) | {"reconnect_ok": success}


@router.post("/{server_id}/toggle")
async def toggle_mcp_server(server_id: int, db=Depends(get_db), mcp_manager=Depends(get_mcp_manager)):
    server = await db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    new_enabled = not bool(server.get("enabled"))
    server = await db.update_mcp_server(server_id, enabled=new_enabled)
    if mcp_manager:
        if new_enabled:
            await mcp_manager.connect(server)
        else:
            await mcp_manager.disconnect(server["name"])
    return _with_status(server, mcp_manager)