"""
Smoke tests：验证 app 生命周期 + 会话 CRUD + 文件树端点 + 工具注册。
不依赖 LLM 网络调用。
"""
from __future__ import annotations


class TestAppLifespan:
    async def test_app_starts_and_shuts_down(self, app_instance):
        """lifespan 能启动就说明 Agent/Scheduler/MCP/DB 都 init 成功了。"""
        assert app_instance.state.agent is not None
        assert app_instance.state.config is not None
        assert app_instance.state.scheduler is not None


class TestSessionCRUD:
    async def test_create_get_delete_session(self, client):
        # 创建
        r = await client.post("/api/sessions", json={"title": "test-session"})
        assert r.status_code == 200, r.text
        session = r.json()
        sid = session["id"]
        assert session["title"] == "test-session"

        # 列表
        r = await client.get("/api/sessions")
        assert r.status_code == 200
        assert any(s["id"] == sid for s in r.json()["sessions"])

        # 读消息（应为空）
        r = await client.get(f"/api/sessions/{sid}/messages")
        assert r.status_code == 200
        assert r.json()["messages"] == []

        # 改标题
        r = await client.put(f"/api/sessions/{sid}/title", json={"title": "renamed"})
        assert r.status_code == 200

        # 删除
        r = await client.delete(f"/api/sessions/{sid}")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # 404 情况
        r = await client.get(f"/api/sessions/{sid}/messages")
        assert r.status_code == 404


class TestFileEndpoints:
    async def test_list_files_default_workspace(self, client, tmp_workspace):
        """默认 workspace 会话（无 working_dir）也能列文件树。"""
        r = await client.post("/api/sessions", json={"title": "fs-test"})
        sid = r.json()["id"]

        r = await client.get(f"/api/sessions/{sid}/files")
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["root"] == str(tmp_workspace.resolve())
        names = [e["name"] for e in payload["entries"]]
        assert "hello.txt" in names

    async def test_file_content_reads_text(self, client, tmp_workspace):
        r = await client.post("/api/sessions", json={"title": "fs-test"})
        sid = r.json()["id"]

        r = await client.get(
            f"/api/sessions/{sid}/file-content",
            params={"path": "hello.txt"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["content"] == "hello world"

    async def test_file_content_rejects_traversal(self, client, tmp_workspace):
        """路径越出根目录必须 400。"""
        r = await client.post("/api/sessions", json={"title": "fs-test"})
        sid = r.json()["id"]

        r = await client.get(
            f"/api/sessions/{sid}/file-content",
            params={"path": "../../../etc/passwd"},
        )
        assert r.status_code == 400

    async def test_files_search(self, client, tmp_workspace):
        r = await client.post("/api/sessions", json={"title": "fs-test"})
        sid = r.json()["id"]

        r = await client.get(
            f"/api/sessions/{sid}/files/search",
            params={"q": "hello"},
        )
        assert r.status_code == 200
        paths = [x["path"] for x in r.json()["results"]]
        assert "hello.txt" in paths


class TestToolRegistry:
    async def test_expected_tools_registered(self, app_instance):
        """核心工具全部注册（避免误删）。"""
        agent = app_instance.state.agent
        tools = agent.tools.list_tools()
        expected = {
            "read_file", "write_file", "edit_file", "list_dir", "read_skill",
            "glob", "grep", "multi_edit", "apply_patch",
            "exec", "spawn_background", "read_process_output",
            "kill_process", "list_processes",
            "spawn_subagents",
            "create_task", "list_tasks", "update_task", "delete_task",
        }
        missing = expected - set(tools)
        assert not missing, f"缺失工具: {missing}"

    async def test_result_limits_configured(self):
        from backend.agent.loop import AgentLoop
        assert AgentLoop._result_limit("read_file") == 40000
        assert AgentLoop._result_limit("exec") == 10000
        # 未列出的走默认
        assert AgentLoop._result_limit("some_unknown_tool") == AgentLoop.TOOL_RESULT_MAX_CHARS


class TestMdCache:
    async def test_agents_md_cache_invalidates_on_mtime(self, tmp_workspace, monkeypatch):
        """AGENTS.md 编辑后 lru_cache 应自动失效。"""
        from backend.agent.context import _read_config_md
        from pathlib import Path
        import time

        md = Path(tmp_workspace).parent / "cfg" / "AGENTS.md"
        md.write_text("v1", encoding="utf-8")

        assert _read_config_md(md) == "v1"

        # 强制 mtime 递增（某些文件系统 mtime 精度较粗）
        time.sleep(0.01)
        md.write_text("v2", encoding="utf-8")
        # touch mtime 保证变化
        stat = md.stat()
        import os
        os.utime(md, (stat.st_atime, stat.st_mtime + 1))

        assert _read_config_md(md) == "v2"
