"""
pytest 全局配置：
- 每个 test 隔离一份临时 workspace + 数据库
- 通过 monkeypatch 环境变量把配置指向 tmp
"""
from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio


@pytest.fixture
def tmp_workspace(monkeypatch, tmp_path: Path) -> Path:
    """独立 workspace + config_dir + skills_dir + DB，避免测试污染彼此。"""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "hello.txt").write_text("hello world", encoding="utf-8")

    cfg = tmp_path / "cfg"
    cfg.mkdir()

    skills = tmp_path / "skills"
    skills.mkdir()

    user_skills = tmp_path / "user_skills"
    user_skills.mkdir()

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # AppConfig 的路径字段（无 env_prefix，直接大写字段名可覆盖）
    monkeypatch.setenv("WORKSPACE", str(ws))
    monkeypatch.setenv("CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SKILLS_DIR", str(skills))
    monkeypatch.setenv("USER_SKILLS_DIR", str(user_skills))
    monkeypatch.setenv("LLM__API_KEY", "test-fake-key")

    # database.DB_PATH 是模块级常量，直接 monkeypatch
    from backend import database as _db_mod
    monkeypatch.setattr(_db_mod, "DB_PATH", data_dir / "agent.db")

    return ws


@pytest_asyncio.fixture
async def app_instance(tmp_workspace):
    """构造并 lifespan-init 一次 FastAPI app。"""
    # 每个测试独立导入避免全局状态污染
    from backend.main import app

    cm = app.router.lifespan_context(app)
    await cm.__aenter__()
    try:
        yield app
    finally:
        await cm.__aexit__(None, None, None)


@pytest_asyncio.fixture
async def client(app_instance):
    """异步 HTTP client，走 ASGI 直连，不启网络端口。"""
    import httpx

    transport = httpx.ASGITransport(app=app_instance)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
