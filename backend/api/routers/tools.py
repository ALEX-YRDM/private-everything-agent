import json as _json
from fastapi import APIRouter, HTTPException, Depends

from ..deps import get_agent, get_db

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
async def list_tools(agent=Depends(get_agent)):
    return {"tools": agent.tools.list_tools()}


@router.get("/state")
async def get_tool_states(session_id: str | None = None,
                          agent=Depends(get_agent), db=Depends(get_db)):
    session_overrides: dict[str, bool] = {}
    if session_id:
        meta = await db.get_session_metadata(session_id)
        session_overrides = meta.get("tool_overrides", {})
    states = agent.tools.get_tool_states(session_overrides=session_overrides)
    return {
        "tools": states,
        "globally_disabled": agent.tools.get_globally_disabled(),
        "session_overrides": session_overrides,
    }


@router.put("/{tool_name}/global")
async def toggle_tool_global(tool_name: str, agent=Depends(get_agent), db=Depends(get_db)):
    if tool_name not in agent.tools.list_tools():
        raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 不存在")
    new_enabled = agent.tools.toggle_global(tool_name)
    disabled_list = agent.tools.get_globally_disabled()
    await db.set_setting("disabled_tools", _json.dumps(disabled_list))
    return {"tool": tool_name, "globally_enabled": new_enabled}