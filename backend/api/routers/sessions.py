from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..deps import get_agent, get_db, get_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str = "新会话"
    model: str | None = None


class UpdateTitleRequest(BaseModel):
    title: str


class SessionModelRequest(BaseModel):
    model: str | None = None


@router.get("")
async def list_sessions(sessions=Depends(get_sessions)):
    return {"sessions": await sessions.list_sessions()}


@router.post("")
async def create_session(body: CreateSessionRequest, sessions=Depends(get_sessions)):
    session = await sessions.create_session(title=body.title, model=body.model)
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str, sessions=Depends(get_sessions)):
    ok = await sessions.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.get("/{session_id}/messages")
async def get_messages(session_id: str, sessions=Depends(get_sessions)):
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = await sessions.get_messages_for_display(session_id)
    return {"messages": messages}


@router.get("/{session_id}/subagent-sessions")
async def get_subagent_sessions(session_id: str, sessions=Depends(get_sessions)):
    result = await sessions.get_subagent_sessions(session_id)
    return {"sessions": result}


@router.put("/{session_id}/title")
async def update_title(session_id: str, body: UpdateTitleRequest, sessions=Depends(get_sessions)):
    ok = await sessions.update_title(session_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.put("/{session_id}/model")
async def set_session_model(session_id: str, body: SessionModelRequest,
                            sessions=Depends(get_sessions), db=Depends(get_db)):
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.execute(
        "UPDATE sessions SET model = ? WHERE id = ?",
        (body.model, session_id),
    )
    return {"session_id": session_id, "model": body.model}


@router.put("/{session_id}/tool-overrides")
async def set_session_tool_overrides(session_id: str,
                                     body: dict,
                                     sessions=Depends(get_sessions),
                                     db=Depends(get_db)):
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    new_overrides: dict[str, bool | None] = body.get("overrides", {})
    meta = await db.get_session_metadata(session_id)
    current_overrides: dict[str, bool] = meta.get("tool_overrides", {})
    for tool_name, value in new_overrides.items():
        if value is None:
            current_overrides.pop(tool_name, None)
        else:
            current_overrides[tool_name] = bool(value)
    meta["tool_overrides"] = current_overrides
    await db.set_session_metadata(session_id, meta)
    return {"session_id": session_id, "tool_overrides": current_overrides}


@router.get("/{session_id}/tool-overrides")
async def get_session_tool_overrides(session_id: str, db=Depends(get_db)):
    meta = await db.get_session_metadata(session_id)
    return {"session_id": session_id, "tool_overrides": meta.get("tool_overrides", {})}