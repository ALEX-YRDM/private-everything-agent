from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pathlib import Path

from ..deps import get_agent, get_db, get_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str = "新会话"
    model: str | None = None
    working_dir: str | None = None


class UpdateTitleRequest(BaseModel):
    title: str


class SessionModelRequest(BaseModel):
    model: str | None = None


class WorkingDirRequest(BaseModel):
    working_dir: str | None = None


class TrustRequest(BaseModel):
    kind: str  # "path" | "command"
    value: str


@router.get("")
async def list_sessions(sessions=Depends(get_sessions)):
    return {"sessions": await sessions.list_sessions()}


@router.post("")
async def create_session(body: CreateSessionRequest, sessions=Depends(get_sessions)):
    session = await sessions.create_session(
        title=body.title, model=body.model, working_dir=body.working_dir,
    )
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


# ── working_dir ────────────────────────────────────────────────────────────

@router.get("/{session_id}/working-dir")
async def get_working_dir(session_id: str, sessions=Depends(get_sessions)):
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session_id": session_id, "working_dir": session.get("working_dir")}


@router.put("/{session_id}/working-dir")
async def set_working_dir(session_id: str, body: WorkingDirRequest,
                          sessions=Depends(get_sessions)):
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    wd = (body.working_dir or "").strip() or None
    if wd is not None:
        p = Path(wd).expanduser()
        if not p.is_absolute():
            raise HTTPException(status_code=400, detail="working_dir 必须是绝对路径")
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"目录不存在: {p}")
        if not p.is_dir():
            raise HTTPException(status_code=400, detail=f"路径不是目录: {p}")
        wd = str(p.resolve())

    await sessions.set_working_dir(session_id, wd)
    return {"session_id": session_id, "working_dir": wd}


# ── trusts ─────────────────────────────────────────────────────────────────

@router.get("/{session_id}/trusts")
async def get_trusts(session_id: str, sessions=Depends(get_sessions)):
    return {"session_id": session_id, **await sessions.get_trusts(session_id)}


@router.put("/{session_id}/trusts")
async def add_trust(session_id: str, body: TrustRequest, sessions=Depends(get_sessions)):
    if body.kind == "path":
        await sessions.add_trusted_path(session_id, body.value)
    elif body.kind == "command":
        await sessions.add_trusted_command(session_id, body.value)
    else:
        raise HTTPException(status_code=400, detail="kind 必须是 'path' 或 'command'")
    return {"session_id": session_id, **await sessions.get_trusts(session_id)}


@router.delete("/{session_id}/trusts")
async def delete_trust(session_id: str, body: TrustRequest, sessions=Depends(get_sessions)):
    if body.kind == "path":
        await sessions.remove_trusted_path(session_id, body.value)
    elif body.kind == "command":
        await sessions.remove_trusted_command(session_id, body.value)
    else:
        raise HTTPException(status_code=400, detail="kind 必须是 'path' 或 'command'")
    return {"session_id": session_id, **await sessions.get_trusts(session_id)}


# ── files (file tree data source) ──────────────────────────────────────────

@router.get("/{session_id}/files")
async def list_files(session_id: str, path: str = "", depth: int = 1,
                     sessions=Depends(get_sessions)):
    """
    返回指定路径下的文件/目录列表（供前端文件树使用）。
    - path 为空时列 session.working_dir 根；否则相对 working_dir。
    - depth=1 只列直接子级；懒加载模式默认 depth=1。
    - 服务端应用 .gitignore（若 working_dir 是 git 仓库根）。
    - 校验 path 不越出 working_dir。
    """
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    root = session.get("working_dir")
    if not root:
        raise HTTPException(status_code=400, detail="会话未设置 working_dir")

    root_p = Path(root).resolve()
    target = (root_p / path).resolve() if path else root_p
    try:
        target.relative_to(root_p)
    except ValueError:
        raise HTTPException(status_code=400, detail="路径越出 working_dir")
    if not target.exists():
        raise HTTPException(status_code=404, detail="路径不存在")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="路径不是目录")

    # 尝试加载 .gitignore（若存在）
    ignore_spec = None
    gi = root_p / ".gitignore"
    if gi.exists():
        try:
            import pathspec
            ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", gi.read_text().splitlines())
        except ImportError:
            pass
        except Exception:
            pass

    def _list(dir_path: Path, cur_depth: int) -> list[dict]:
        entries = []
        try:
            items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return entries
        for item in items:
            if item.name in (".git",):
                continue
            rel = str(item.relative_to(root_p))
            if ignore_spec and ignore_spec.match_file(rel + ("/" if item.is_dir() else "")):
                continue
            node = {
                "name": item.name,
                "path": rel,
                "type": "dir" if item.is_dir() else "file",
            }
            if item.is_dir() and cur_depth < depth:
                node["children"] = _list(item, cur_depth + 1)
            entries.append(node)
        return entries

    return {
        "session_id": session_id,
        "root": str(root_p),
        "path": str(target.relative_to(root_p)) if target != root_p else "",
        "entries": _list(target, 1),
    }