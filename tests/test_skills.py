"""Skill 系统重构后的单元测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.agent.skills import (
    SkillsLoader, SkillIndex, _read_skill_frontmatter,
)


@pytest.fixture(autouse=True)
def _clear_skill_cache():
    """每个 test 前后都清一遍 frontmatter 缓存，避免 case 间污染。"""
    _read_skill_frontmatter.cache_clear()
    yield
    _read_skill_frontmatter.cache_clear()


def _write_skill(root: Path, name: str, description: str, extra: str = "") -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    md = d / "SKILL.md"
    md.write_text(
        f"---\nname: {name}\ndescription: {description}\n{extra}---\n\n# {name}\n\nbody\n",
        encoding="utf-8",
    )
    return md


class TestSkillIndex:
    def test_list_dedupes_user_over_builtin(self, tmp_path):
        builtin = tmp_path / "builtin"
        user = tmp_path / "user"
        builtin.mkdir()
        user.mkdir()
        _write_skill(builtin, "alpha", "内置版本")
        _write_skill(user, "alpha", "用户覆盖版本")
        _write_skill(builtin, "beta", "只在内置")

        idx = SkillIndex(builtin, user)
        skills = idx.list()
        names = {s.name: s for s in skills}

        assert set(names) == {"alpha", "beta"}
        assert names["alpha"].tier == "user"
        assert names["alpha"].description == "用户覆盖版本"
        assert names["beta"].tier == "builtin"

    def test_find_prefers_user(self, tmp_path):
        builtin = tmp_path / "b"; builtin.mkdir()
        user = tmp_path / "u"; user.mkdir()
        _write_skill(builtin, "foo", "内置 foo")
        _write_skill(user, "foo", "用户 foo")

        idx = SkillIndex(builtin, user)
        info = idx.find("foo")
        assert info.tier == "user"
        assert info.description == "用户 foo"

    def test_find_returns_none_for_unknown(self, tmp_path):
        idx = SkillIndex(tmp_path / "b", tmp_path / "u")
        assert idx.find("nonexistent") is None

    def test_broken_skill_flagged(self, tmp_path):
        user = tmp_path / "u"; user.mkdir()
        d = user / "bad"
        d.mkdir()
        # 没 frontmatter
        (d / "SKILL.md").write_text("# bad skill\n没有 frontmatter", encoding="utf-8")

        idx = SkillIndex(None, user)
        # 默认过滤掉坏 skill
        assert idx.list() == []
        # 但 include_broken=True 时能看到
        broken = idx.list(include_broken=True)
        assert len(broken) == 1
        assert broken[0].parse_error is not None

    def test_self_referential_description_flagged(self, tmp_path):
        """description 等于 name 视为坏 skill（触发不清晰）。"""
        user = tmp_path / "u"; user.mkdir()
        _write_skill(user, "loop", "loop")  # 自描述

        idx = SkillIndex(None, user)
        assert idx.list() == []
        broken = idx.list(include_broken=True)
        assert len(broken) == 1
        assert "self-referential" in broken[0].parse_error


class TestMtimeInvalidation:
    def test_frontmatter_cache_invalidates_on_mtime(self, tmp_path):
        import time
        import os

        user = tmp_path / "u"; user.mkdir()
        md = _write_skill(user, "mtime-check", "旧描述")

        idx = SkillIndex(None, user)
        info = idx.find("mtime-check")
        assert info.description == "旧描述"

        # 改文件 + 强制 mtime 前进
        time.sleep(0.01)
        _write_skill(user, "mtime-check", "新描述")
        stat = md.stat()
        os.utime(md, (stat.st_atime, stat.st_mtime + 1))

        info2 = idx.find("mtime-check")
        assert info2.description == "新描述"


class TestAvailability:
    def test_missing_bin_marked_but_not_filtered(self, tmp_path):
        user = tmp_path / "u"; user.mkdir()
        _write_skill(
            user, "needs-git",
            "需要一个几乎不存在的 bin",
            extra="requires:\n  bins:\n    - definitely-not-a-real-bin-xyz\n",
        )

        loader = SkillsLoader(None, user)
        skills = loader.list_all()
        assert len(skills) == 1
        s = skills[0]
        assert loader.available(s) is False
        assert "bin:definitely-not-a-real-bin-xyz" in loader.missing(s)

    def test_summary_includes_unavailable_with_flag(self, tmp_path):
        user = tmp_path / "u"; user.mkdir()
        _write_skill(
            user, "no-git", "缺 bin 的技能",
            extra="requires:\n  bins:\n    - definitely-fake-bin-xyz\n",
        )
        loader = SkillsLoader(None, user)
        summary = loader.build_skills_summary()
        # 依然出现在摘要
        assert "no-git" in summary
        # 但显式标 unavailable
        assert 'available="false"' in summary
        assert "definitely-fake-bin-xyz" in summary


class TestCreateUserSkill:
    def test_create_and_read_back(self, tmp_path):
        user = tmp_path / "u"
        loader = SkillsLoader(None, user)

        target = loader.create_user_skill(
            name="my-skill",
            description="我的第一个技能",
            body="## 步骤\n1. 做事",
            when="用户说 xxx 时",
        )
        assert target.exists()

        info = loader.find("my-skill")
        assert info is not None
        assert info.tier == "user"
        assert info.description == "我的第一个技能"
        assert info.when == "用户说 xxx 时"

    def test_reject_invalid_name(self, tmp_path):
        loader = SkillsLoader(None, tmp_path / "u")
        with pytest.raises(ValueError, match="kebab-case"):
            loader.create_user_skill("Bad_Name!", "desc", "body")

    def test_reject_empty_description(self, tmp_path):
        loader = SkillsLoader(None, tmp_path / "u")
        with pytest.raises(ValueError, match="description"):
            loader.create_user_skill("ok-name", "", "body")

    def test_reject_self_referential_description(self, tmp_path):
        loader = SkillsLoader(None, tmp_path / "u")
        with pytest.raises(ValueError, match="不能与 name 相同"):
            loader.create_user_skill("ok-name", "ok-name", "body")

    def test_reject_overwrite_builtin(self, tmp_path):
        builtin = tmp_path / "b"; builtin.mkdir()
        _write_skill(builtin, "existing", "内置")
        loader = SkillsLoader(builtin, tmp_path / "u")
        with pytest.raises(ValueError, match="内置 skill"):
            loader.create_user_skill("existing", "试图覆盖", "body")

    def test_reject_duplicate_without_overwrite(self, tmp_path):
        user = tmp_path / "u"
        loader = SkillsLoader(None, user)
        loader.create_user_skill("dup", "first", "body")
        with pytest.raises(ValueError, match="已存在"):
            loader.create_user_skill("dup", "second", "body")
        # 显式 overwrite=True 允许
        loader.create_user_skill("dup", "second", "body", overwrite=True)
        assert loader.find("dup").description == "second"


class TestInstallFromPath:
    def test_install_copies_tree(self, tmp_path):
        # 源 skill 目录：含 SKILL.md + 子文件
        src = tmp_path / "src-skill"
        src.mkdir()
        (src / "SKILL.md").write_text(
            "---\nname: src-skill\ndescription: 从外部装的\n---\n\nbody\n",
            encoding="utf-8",
        )
        (src / "scripts").mkdir()
        (src / "scripts" / "run.sh").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")

        user = tmp_path / "u"
        loader = SkillsLoader(None, user)
        target = loader.install_from_path(src)
        assert (target / "SKILL.md").exists()
        assert (target / "scripts" / "run.sh").exists()

        info = loader.find("src-skill")
        assert info is not None

    def test_install_reject_missing_skill_md(self, tmp_path):
        src = tmp_path / "notskill"
        src.mkdir()
        loader = SkillsLoader(None, tmp_path / "u")
        with pytest.raises(ValueError, match="SKILL.md"):
            loader.install_from_path(src)


class TestReadSkillTool:
    """回归：新 read_skill 走 SkillIndex，且支持读子文件。"""

    async def test_read_skill_md_via_tool(self, tmp_path):
        from backend.tools.filesystem import ReadSkillTool

        user = tmp_path / "u"; user.mkdir()
        _write_skill(user, "aaa", "test skill")
        loader = SkillsLoader(None, user)

        tool = ReadSkillTool(loader)
        result = await tool.execute(name="aaa")
        assert "test skill" in result
        assert "body" in result

    async def test_read_subfile(self, tmp_path):
        from backend.tools.filesystem import ReadSkillTool

        user = tmp_path / "u"; user.mkdir()
        _write_skill(user, "sub", "test")
        (user / "sub" / "scripts").mkdir()
        (user / "sub" / "scripts" / "foo.sh").write_text("#!/bin/bash\necho hello\n",
                                                          encoding="utf-8")
        loader = SkillsLoader(None, user)

        tool = ReadSkillTool(loader)
        result = await tool.execute(name="sub", path="scripts/foo.sh")
        assert "echo hello" in result

    async def test_read_subfile_traversal_blocked(self, tmp_path):
        from backend.tools.filesystem import ReadSkillTool

        user = tmp_path / "u"; user.mkdir()
        _write_skill(user, "trv", "test")
        (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
        loader = SkillsLoader(None, user)

        tool = ReadSkillTool(loader)
        result = await tool.execute(name="trv", path="../../secret.txt")
        assert "越出" in result

    async def test_read_missing_skill(self, tmp_path):
        from backend.tools.filesystem import ReadSkillTool

        loader = SkillsLoader(None, tmp_path / "u")
        tool = ReadSkillTool(loader)
        result = await tool.execute(name="nonexistent")
        assert "不存在" in result


class TestSkillsAPI:
    """走完整 HTTP 栈的集成测试：装/列/删。"""

    async def test_list_empty(self, client, tmp_workspace):
        r = await client.get("/api/skills")
        assert r.status_code == 200
        # 空目录 → 空列表（不算错）
        assert isinstance(r.json()["skills"], list)

    async def test_install_from_path_and_delete(self, client, tmp_workspace, tmp_path):
        # 造一个源 skill 目录（目录名 = 最终 skill 名）
        src = tmp_path / "hello-skill"
        src.mkdir()
        (src / "SKILL.md").write_text(
            "---\nname: hello-skill\ndescription: 打招呼\n---\n\n打招呼\n",
            encoding="utf-8",
        )
        # 装
        r = await client.post("/api/skills/install", json={
            "source": "path",
            "location": str(src),
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["skill"]["name"] == "hello-skill"
        assert body["skill"]["tier"] == "user"

        # 列
        r = await client.get("/api/skills")
        assert r.status_code == 200
        names = [s["name"] for s in r.json()["skills"]]
        assert "hello-skill" in names

        # 详情
        r = await client.get("/api/skills/hello-skill")
        assert r.status_code == 200
        assert "打招呼" in r.json()["content"]

        # 删
        r = await client.delete("/api/skills/hello-skill")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # 再列，已经不在了
        r = await client.get("/api/skills")
        names2 = [s["name"] for s in r.json()["skills"]]
        assert "hello-skill" not in names2

    async def test_install_bad_source_400(self, client, tmp_workspace):
        r = await client.post("/api/skills/install", json={
            "source": "unknown",
            "location": "irrelevant",
        })
        assert r.status_code == 400

    async def test_legacy_endpoints_still_work(self, client, tmp_workspace):
        """老前端仍在用 /skills/system 和 /skills/user，不能破坏。"""
        r1 = await client.get("/api/skills/system")
        assert r1.status_code == 200
        r2 = await client.get("/api/skills/user")
        assert r2.status_code == 200
