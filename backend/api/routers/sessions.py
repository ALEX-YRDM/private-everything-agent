from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pathlib import Path

from ..deps import get_agent, get_db, get_sessions, get_config

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


class SummaryBody(BaseModel):
    summary: str


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
                     sessions=Depends(get_sessions), config=Depends(get_config)):
    """
    返回指定路径下的文件/目录列表（供前端文件树使用）。
    - path 为空时列会话的根目录（session.working_dir，未绑定时 fallback 到 config.workspace）
    - depth=1 只列直接子级；懒加载模式默认 depth=1。
    - 服务端应用 .gitignore（若根目录是 git 仓库根）。
    - 校验 path 不越出根目录。
    """
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    root = session.get("working_dir") or config.workspace
    if not root:
        raise HTTPException(status_code=400, detail="工作目录未配置")

    root_p = Path(root).expanduser().resolve()
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


# ── file content (只读预览) ────────────────────────────────────────────────

def _session_root(session: dict, config) -> str:
    """
    解析会话的根目录：优先 working_dir，未绑定时 fallback 到 config.workspace。
    找不到就报 400（config.workspace 默认存在，通常不会走到）。
    """
    root = session.get("working_dir") or config.workspace
    if not root:
        raise HTTPException(status_code=400, detail="工作目录未配置")
    return root


def _resolve_under_root(session: dict, config, rel_path: str) -> Path:
    """把会话相对路径解析为绝对路径，校验不越出根目录。"""
    root = _session_root(session, config)
    root_p = Path(root).expanduser().resolve()
    target = (root_p / rel_path).resolve() if rel_path else root_p
    try:
        target.relative_to(root_p)
    except ValueError:
        raise HTTPException(status_code=400, detail="路径越出工作目录")
    return target


@router.get("/{session_id}/file-content")
async def get_file_content(session_id: str, path: str, max_bytes: int = 524288,
                           sessions=Depends(get_sessions), config=Depends(get_config)):
    """读文本文件（供代码浏览器只读预览）。二进制自动识别并拒绝。"""
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not path:
        raise HTTPException(status_code=400, detail="path 不能为空")

    target = _resolve_under_root(session, config, path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="路径不是文件")

    size = target.stat().st_size
    read_bytes = min(size, max_bytes)
    try:
        with target.open("rb") as f:
            raw = f.read(read_bytes)
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权读取")

    # 二进制探测：前 4KB 内有 NUL 字节视为二进制
    if b"\x00" in raw[:4096]:
        raise HTTPException(status_code=415, detail="二进制文件不支持预览")

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")

    return {
        "session_id": session_id,
        "path": path,
        "size": size,
        "truncated": read_bytes < size,
        "content": content,
    }


# ── files/search (@ 补全数据源) ────────────────────────────────────────────

_FILE_SEARCH_MAX_SCAN = 20000
_SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".nuxt", ".turbo", ".cache", ".pytest_cache", ".mypy_cache",
    "target", ".idea", ".vscode",
}


@router.get("/{session_id}/files/search")
async def search_files(session_id: str, q: str = "", limit: int = 30,
                       sessions=Depends(get_sessions), config=Depends(get_config)):
    """扁平文件模糊搜索（供 @ 补全）。"""
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    root = session.get("working_dir") or config.workspace
    if not root:
        return {"session_id": session_id, "query": q, "results": [], "truncated": False}

    root_p = Path(root).expanduser().resolve()
    q_norm = (q or "").strip().lower()

    # 尝试加载 .gitignore
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

    results: list[dict] = []
    scanned = 0
    truncated = False

    def _walk(dir_p: Path):
        nonlocal scanned, truncated
        if truncated:
            return
        try:
            items = list(dir_p.iterdir())
        except (PermissionError, OSError):
            return
        for item in items:
            scanned += 1
            if scanned > _FILE_SEARCH_MAX_SCAN:
                truncated = True
                return
            if item.name in _SKIP_DIRS:
                continue
            try:
                rel = str(item.relative_to(root_p))
            except ValueError:
                continue
            if ignore_spec and ignore_spec.match_file(rel + ("/" if item.is_dir() else "")):
                continue
            if item.is_dir():
                _walk(item)
            else:
                if not q_norm or q_norm in item.name.lower() or q_norm in rel.lower():
                    results.append({"path": rel, "name": item.name})
                    if len(results) >= limit:
                        truncated = True
                        return

    _walk(root_p)

    return {
        "session_id": session_id,
        "query": q,
        "results": results,
        "truncated": truncated,
    }


# ── git status (文件树徽章) ────────────────────────────────────────────────

_GIT_STATUS_CACHE: dict[str, tuple[float, dict]] = {}
_GIT_STATUS_TTL = 60.0  # 秒


@router.get("/{session_id}/git-status")
async def git_status(session_id: str, sessions=Depends(get_sessions), config=Depends(get_config)):
    """返回根目录的 git 分支 + porcelain 状态（60s 内存缓存）。"""
    import asyncio as _aio
    import time

    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    root = session.get("working_dir") or config.workspace
    if not root:
        return {"is_git": False, "branch": None, "files": {}, "counts": {}}

    root_p = Path(root).expanduser().resolve()
    cache_key = str(root_p)
    now = time.time()
    hit = _GIT_STATUS_CACHE.get(cache_key)
    if hit and (now - hit[0]) < _GIT_STATUS_TTL:
        return hit[1]

    if not (root_p / ".git").exists():
        result = {"is_git": False, "branch": None, "files": {}, "counts": {}}
        _GIT_STATUS_CACHE[cache_key] = (now, result)
        return result

    async def _run(*args: str) -> tuple[int, str, str]:
        proc = await _aio.create_subprocess_exec(
            *args,
            cwd=str(root_p),
            stdout=_aio.subprocess.PIPE,
            stderr=_aio.subprocess.PIPE,
        )
        try:
            out, err = await _aio.wait_for(proc.communicate(), timeout=5.0)
        except _aio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, "", "timeout"
        return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")

    # branch
    rc, branch_out, _ = await _run("git", "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_out.strip() if rc == 0 else None

    # porcelain
    rc, po_out, _ = await _run("git", "status", "--porcelain", "-z")
    files: dict[str, str] = {}
    counts: dict[str, int] = {}
    if rc == 0 and po_out:
        # porcelain -z 用 NUL 分隔，前两列是状态码
        for entry in po_out.split("\x00"):
            if len(entry) < 3:
                continue
            code = entry[:2]
            path_part = entry[3:]
            # 取重命名箭头后的目标路径（rename 情况：`R  old -> new`；-z 时改成两段但简化处理）
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1]
            simple = code.strip()[:1] or "?"
            if simple == "?":
                simple = "?"
            files[path_part] = simple
            counts[simple] = counts.get(simple, 0) + 1

    result = {
        "is_git": True,
        "branch": branch,
        "files": files,
        "counts": counts,
    }
    _GIT_STATUS_CACHE[cache_key] = (now, result)
    return result


# ── 会话导出为 Markdown ────────────────────────────────────────────────────

def _export_session_to_markdown(session: dict, messages: list[dict]) -> str:
    """把会话消息渲染成一份可读性优先的 Markdown 文档。"""
    import json as _json
    lines: list[str] = []
    title = session.get("title") or session.get("id")
    lines.append(f"# {title}")
    lines.append("")
    meta_bits = []
    if session.get("created_at"):
        meta_bits.append(f"创建于 {session['created_at']}")
    if session.get("model"):
        meta_bits.append(f"模型：{session['model']}")
    if session.get("working_dir"):
        meta_bits.append(f"工作目录：`{session['working_dir']}`")
    if meta_bits:
        lines.append("> " + " · ".join(meta_bits))
        lines.append("")

    for msg in messages:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role == "user":
            lines.append("## 👤 用户")
            lines.append("")
            if content:
                lines.append(content)
                lines.append("")
        elif role == "assistant":
            lines.append("## 🤖 助手")
            lines.append("")
            reasoning = msg.get("reasoning")
            if reasoning:
                lines.append("<details><summary>思维链</summary>")
                lines.append("")
                lines.append(reasoning.strip())
                lines.append("")
                lines.append("</details>")
                lines.append("")
            if content:
                lines.append(content)
                lines.append("")
            tc_raw = msg.get("tool_calls")
            if tc_raw:
                try:
                    tool_calls = _json.loads(tc_raw) if isinstance(tc_raw, str) else tc_raw
                except Exception:
                    tool_calls = []
                for tc in (tool_calls or []):
                    name = tc.get("name", "?")
                    args = tc.get("arguments") or tc.get("args") or {}
                    if isinstance(args, str):
                        args_preview = args
                    else:
                        try:
                            args_preview = _json.dumps(args, ensure_ascii=False, indent=2)
                        except Exception:
                            args_preview = str(args)
                    lines.append(f"<details><summary>🔧 工具调用：<code>{name}</code></summary>")
                    lines.append("")
                    lines.append("```json")
                    lines.append(args_preview)
                    lines.append("```")
                    lines.append("")
                    lines.append("</details>")
                    lines.append("")
            usage_bits = []
            if msg.get("input_tokens") is not None:
                usage_bits.append(f"input {msg['input_tokens']}")
            if msg.get("output_tokens") is not None:
                usage_bits.append(f"output {msg['output_tokens']}")
            if usage_bits:
                lines.append(f"<sub>tokens · {' · '.join(usage_bits)}</sub>")
                lines.append("")
        elif role == "tool":
            tool_name = msg.get("tool_name") or "工具"
            lines.append(f"<details><summary>↳ 工具结果：<code>{tool_name}</code></summary>")
            lines.append("")
            lines.append("```")
            lines.append(content or "(空)")
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")
        else:
            # system / 其它角色一般不展示；如遇到留个可折叠标记
            lines.append(f"<details><summary>{role or 'system'}</summary>")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("</details>")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@router.get("/{session_id}/export")
async def export_session(session_id: str, format: str = "md",
                         sessions=Depends(get_sessions)):
    """
    导出会话为 Markdown / JSON。
    - format=md（默认）：可读性优先的 Markdown，工具调用折叠
    - format=json：原始 messages（不含 system prompt）
    """
    from fastapi.responses import PlainTextResponse, JSONResponse
    import re as _re

    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = await sessions.get_messages_for_display(session_id)

    if format == "json":
        return JSONResponse({
            "session": dict(session),
            "messages": [dict(m) for m in messages],
        })
    if format != "md":
        raise HTTPException(status_code=400, detail="format 只支持 md / json")

    body = _export_session_to_markdown(dict(session), [dict(m) for m in messages])

    # 文件名：会话标题 → 安全化
    safe_title = _re.sub(r"[^\w一-龥\-_. ]+", "_", session.get("title") or session_id).strip("_ ") or session_id
    filename = f"{safe_title}.md"
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename*=UTF-8\'\'{filename}'},
    )


# ── 会话摘要（AutoCompact 产物）读写 ────────────────────────────────────────

@router.get("/{session_id}/summary")
async def get_session_summary(session_id: str,
                              sessions=Depends(get_sessions),
                              db=Depends(get_db)):
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    row = await db.fetch_one("SELECT summary FROM sessions WHERE id = ?", (session_id,))
    return {"session_id": session_id, "summary": (row or {}).get("summary") or ""}


@router.put("/{session_id}/summary")
async def set_session_summary(session_id: str, body: SummaryBody,
                              sessions=Depends(get_sessions),
                              db=Depends(get_db)):
    session = await sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.execute(
        "UPDATE sessions SET summary = ? WHERE id = ?",
        (body.summary, session_id),
    )
    return {"session_id": session_id, "summary": body.summary}