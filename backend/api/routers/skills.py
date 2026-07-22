from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_agent

router = APIRouter(prefix="/skills", tags=["skills"])


def _info_to_dict(loader, info) -> dict:
    return {
        "name": info.name,
        "description": info.description,
        "tier": info.tier,
        "when": info.when,
        "path": str(info.path),
        "available": loader.available(info),
        "missing": loader.missing(info),
        "requires_bins": info.requires_bins,
        "requires_env": info.requires_env,
        "parse_error": info.parse_error,
    }


@router.get("")
async def list_skills(include_broken: bool = False, agent=Depends(get_agent)):
    """列出所有 skills，含 tier / available / missing 信息。"""
    loader = agent.context.skills
    skills = loader.list_all(include_broken=include_broken)
    return {"skills": [_info_to_dict(loader, s) for s in skills]}


# ── 旧接口兼容层（前端后续统一到新 GET /skills；必须放在 /{name} 之前） ──

@router.get("/system")
async def list_system_skills_legacy(agent=Depends(get_agent)):
    loader = agent.context.skills
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "available": loader.available(s),
                "requires_bins": s.requires_bins,
                "requires_env": s.requires_env,
            }
            for s in loader.list_all() if s.tier == "builtin"
        ]
    }


@router.get("/user")
async def list_user_skills_legacy(agent=Depends(get_agent)):
    loader = agent.context.skills
    return {
        "skills": [
            {"name": s.name, "description": s.description, "path": str(s.path)}
            for s in loader.list_all() if s.tier == "user"
        ]
    }


# ── 安装 / 删除 ────────────────────────────────────────────────────────

class InstallRequest(BaseModel):
    source: str  # "path" | "git"
    location: str  # path=本地目录，git=git URL
    name: str | None = None  # 可选，覆盖默认名字
    overwrite: bool = False


@router.post("/install")
async def install_skill(req: InstallRequest, agent=Depends(get_agent)):
    """从本地目录或 git URL 安装 skill 到 user tier。"""
    loader = agent.context.skills
    if req.source == "path":
        try:
            target = loader.install_from_path(
                Path(req.location), name=req.name, overwrite=req.overwrite,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif req.source == "git":
        try:
            target = _install_from_git(loader, req.location, req.name, req.overwrite)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail=f"未知 source: {req.source}")

    name = target.name
    info = loader.find(name)
    return {
        "ok": True,
        "installed_at": str(target),
        "skill": _info_to_dict(loader, info) if info else None,
    }


# ── 详情 / 删除（动态路径放最后，避免吞掉 /system /user /install） ──

@router.get("/{name}")
async def get_skill(name: str, agent=Depends(get_agent)):
    """读单个 skill 的完整 SKILL.md 内容（供前端预览）。"""
    loader = agent.context.skills
    info = loader.find(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"skill '{name}' 不存在")
    try:
        content = info.path.read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"读取失败：{e}")
    return {**_info_to_dict(loader, info), "content": content}


@router.delete("/{name}")
async def delete_skill(name: str, agent=Depends(get_agent)):
    """删除 user tier 下的 skill（不能删 builtin）。"""
    loader = agent.context.skills
    info = loader.find(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"skill '{name}' 不存在")
    if info.tier == "builtin":
        raise HTTPException(status_code=403, detail="不能删除 builtin skill")
    try:
        removed = loader.delete_user_skill(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "removed": removed}


# ── helpers ────────────────────────────────────────────────────────────

def _install_from_git(loader, url: str, name: str | None, overwrite: bool) -> Path:
    """git clone URL 到临时目录 → install_from_path 到 user tier。"""
    import subprocess
    import tempfile
    import shutil as _sh

    with tempfile.TemporaryDirectory() as tmp:
        tmp_target = Path(tmp) / "skill"
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", url, str(tmp_target)],
                check=True, capture_output=True, timeout=60,
            )
        except FileNotFoundError:
            raise ValueError("未找到 git 可执行文件")
        except subprocess.TimeoutExpired:
            raise ValueError("git clone 超时（60 秒）")
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"").decode("utf-8", errors="replace")[:500]
            raise ValueError(f"git clone 失败：{stderr.strip() or '未知错误'}")

        # git clone 会带 .git 目录，删掉再复制
        git_dir = tmp_target / ".git"
        if git_dir.exists():
            _sh.rmtree(git_dir, ignore_errors=True)

        # 复用 install_from_path 做统一校验 + 复制
        return loader.install_from_path(tmp_target, name=name, overwrite=overwrite)
