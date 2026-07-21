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


class TestExport:
    async def test_export_markdown(self, client):
        r = await client.post("/api/sessions", json={"title": "export-test"})
        sid = r.json()["id"]

        r = await client.get(f"/api/sessions/{sid}/export", params={"format": "md"})
        assert r.status_code == 200
        assert "text/markdown" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]
        body = r.text
        assert "# export-test" in body

    async def test_export_markdown_chinese_title(self, client):
        """回归：中文标题走 RFC 5987 编码，不再触发 latin-1 UnicodeEncodeError。"""
        r = await client.post("/api/sessions", json={"title": "梦蝶的会话"})
        sid = r.json()["id"]

        r = await client.get(f"/api/sessions/{sid}/export", params={"format": "md"})
        assert r.status_code == 200
        cd = r.headers["content-disposition"]
        # 中文文件名必须以 percent-encoded 形式出现
        assert "filename*=UTF-8''" in cd
        # 原文中文不能出现在 header 里（否则又要爆）
        assert "梦蝶" not in cd

    async def test_export_json(self, client):
        r = await client.post("/api/sessions", json={"title": "j-test"})
        sid = r.json()["id"]

        r = await client.get(f"/api/sessions/{sid}/export", params={"format": "json"})
        assert r.status_code == 200
        data = r.json()
        assert data["session"]["title"] == "j-test"
        assert isinstance(data["messages"], list)


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
            "todo_write", "todo_read",
            "enter_plan_mode", "exit_plan_mode",
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


class TestOrphanToolCallPatch:
    """回归：断线时 assistant.tool_calls 已落盘但 tool 响应未生成，
    下一次调用必须能自愈，不能把孤儿 tool_call 喂给 provider 触发 400。"""

    def test_orphan_tool_call_is_patched(self):
        from backend.session.manager import SessionManager
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "exec", "arguments": "{}"}},
            ]},
        ]
        patched = SessionManager._patch_orphan_tool_calls(messages)
        assert len(patched) == 3
        tail = patched[-1]
        assert tail["role"] == "tool"
        assert tail["tool_call_id"] == "call_1"
        assert tail["name"] == "exec"
        assert "未执行" in tail["content"]

    def test_intact_tool_call_untouched(self):
        from backend.session.manager import SessionManager
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "exec", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "call_1", "name": "exec", "content": "ok"},
        ]
        patched = SessionManager._patch_orphan_tool_calls(messages)
        assert patched == messages

    def test_partial_orphan_only_patches_missing(self):
        """两个 tool_call，只有一个有响应 → 只补另一个。"""
        from backend.session.manager import SessionManager
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "read_file", "arguments": "{}"}},
                {"id": "call_2", "type": "function",
                 "function": {"name": "exec", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "call_1", "name": "read_file", "content": "..."},
        ]
        patched = SessionManager._patch_orphan_tool_calls(messages)
        # 顺序：user, assistant, tool(call_1 已有), tool(call_2 补齐)
        assert len(patched) == 4
        assert patched[3]["role"] == "tool"
        assert patched[3]["tool_call_id"] == "call_2"
        assert patched[3]["name"] == "exec"

    def test_flat_shape_tool_call_name_fallback(self):
        """兼容旧数据可能扁平存 {name, arguments}。"""
        from backend.session.manager import SessionManager
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "name": "exec", "arguments": "{}"},
            ]},
        ]
        patched = SessionManager._patch_orphan_tool_calls(messages)
        assert patched[-1]["name"] == "exec"


class TestStripThinkTags:
    """标题生成时部分模型会把 reasoning 泄到 content 里（DeepSeek-R1 等）。"""

    def test_full_think_block_removed(self):
        from backend.agent.loop import _strip_think_tags
        text = "<think>\nLet me think...\n多行推理\n</think>\n简单问候互动"
        assert _strip_think_tags(text) == "简单问候互动"

    def test_unclosed_think_dropped_to_eof(self):
        """有开无闭：从 <think> 到末尾都丢，避免半截推理泄漏。"""
        from backend.agent.loop import _strip_think_tags
        text = "友好问候<think>没写完就被截断"
        assert _strip_think_tags(text) == "友好问候"

    def test_no_think_untouched(self):
        from backend.agent.loop import _strip_think_tags
        assert _strip_think_tags("普通标题") == "普通标题"

    def test_stray_close_tag_removed(self):
        from backend.agent.loop import _strip_think_tags
        assert _strip_think_tags("标题</think>") == "标题"

    def test_empty_input(self):
        from backend.agent.loop import _strip_think_tags
        assert _strip_think_tags("") == ""


class TestCtxInjection:
    """回归：MCP 工具 execute(**kwargs) 只是为了透传远端参数，不吃 _ctx。
    registry 之前把所有 **kwargs 工具都塞 _ctx，导致 MCP 报 Unknown argument。"""

    async def test_receives_ctx_false_skips_injection(self):
        from backend.tools.registry import ToolRegistry
        from backend.tools.context import ToolContext
        from backend.tools.base import Tool
        from pathlib import Path

        class FakeMCP(Tool):
            _receives_ctx = False
            name = "fake_mcp_tool"
            description = "..."
            parameters = {"type": "object", "properties": {}}
            async def execute(self, **kwargs):
                return str(sorted(kwargs.keys()))

        reg = ToolRegistry()
        reg.register(FakeMCP())
        ctx = ToolContext(cwd=Path("/tmp"), session_id="s1",
                          sandbox_mode="free", trusted_paths=[], trusted_commands=[])
        out = await reg.execute("fake_mcp_tool", {"url": "https://x"}, session_ctx=ctx)
        # _ctx 不应该出现在 kwargs 里
        assert "_ctx" not in out
        assert "url" in out

    async def test_native_kwargs_tool_still_gets_ctx(self):
        """反向验证：没标 _receives_ctx=False 的 **kwargs 工具仍能拿到 _ctx。"""
        from backend.tools.registry import ToolRegistry
        from backend.tools.context import ToolContext
        from backend.tools.base import Tool
        from pathlib import Path

        class KwargsTool(Tool):
            name = "kwargs_tool"
            description = "..."
            parameters = {"type": "object", "properties": {}}
            async def execute(self, **kwargs):
                return "yes" if "_ctx" in kwargs else "no"

        reg = ToolRegistry()
        reg.register(KwargsTool())
        ctx = ToolContext(cwd=Path("/tmp"), session_id="s1",
                          sandbox_mode="free", trusted_paths=[], trusted_commands=[])
        out = await reg.execute("kwargs_tool", {}, session_ctx=ctx)
        assert out == "yes"
