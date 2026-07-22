"""mengdie CLI 测试。"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from backend.cli import main, INSTALL_SOURCE_FILE, _looks_like_git_url, _basename_from_url


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    """把 user tier 指向 tmp 目录，避免污染真实 ~/.mengdie/skills/。"""
    d = tmp_path / "user_skills"
    d.mkdir()
    monkeypatch.setenv("USER_SKILLS_DIR", str(d))
    return d


def _make_src_skill(root: Path, name: str, description: str) -> Path:
    d = root / name
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nbody\n",
        encoding="utf-8",
    )
    return d


class TestUrlHelpers:
    def test_git_url_detection(self):
        assert _looks_like_git_url("https://github.com/x/y.git")
        assert _looks_like_git_url("git@github.com:x/y.git")
        assert _looks_like_git_url("ssh://user@host/x.git")
        assert not _looks_like_git_url("/abs/path")
        assert not _looks_like_git_url("./local")
        assert not _looks_like_git_url("relative/dir")

    def test_basename_extraction(self):
        assert _basename_from_url("https://github.com/foo/my-skill.git") == "my-skill"
        assert _basename_from_url("https://github.com/foo/my-skill") == "my-skill"
        assert _basename_from_url("git@github.com:foo/my-skill.git") == "my-skill"
        assert _basename_from_url("https://x/foo/") == "foo"


class TestInstallLocalPath:
    def test_install_from_local(self, user_dir, tmp_path, capsys):
        src = _make_src_skill(tmp_path, "local-skill", "本地装的")
        rc = main(["skill", "install", str(src)])
        assert rc == 0
        assert (user_dir / "local-skill" / "SKILL.md").exists()
        # 源标记落盘
        marker = user_dir / "local-skill" / INSTALL_SOURCE_FILE
        assert marker.exists()
        assert str(src) in marker.read_text(encoding="utf-8")

    def test_install_reject_duplicate(self, user_dir, tmp_path):
        src = _make_src_skill(tmp_path, "dup", "第一次")
        main(["skill", "install", str(src)])
        # 第二次装同名，应该报错
        with pytest.raises(SystemExit, match="已存在"):
            main(["skill", "install", str(src)])

    def test_install_force_overwrites(self, user_dir, tmp_path):
        src = _make_src_skill(tmp_path, "force-me", "v1")
        main(["skill", "install", str(src)])
        # 改源，force 装
        (src / "SKILL.md").write_text(
            "---\nname: force-me\ndescription: v2\n---\n\nbody\n",
            encoding="utf-8",
        )
        rc = main(["skill", "install", str(src), "--force"])
        assert rc == 0
        content = (user_dir / "force-me" / "SKILL.md").read_text(encoding="utf-8")
        assert "v2" in content

    def test_install_with_custom_name(self, user_dir, tmp_path):
        src = _make_src_skill(tmp_path, "orig-name", "改名字")
        rc = main(["skill", "install", str(src), "--name", "renamed"])
        assert rc == 0
        assert (user_dir / "renamed" / "SKILL.md").exists()
        assert not (user_dir / "orig-name").exists()


class TestList:
    def test_list_empty(self, user_dir, capsys):
        main(["skill", "list"])
        out = capsys.readouterr().out
        assert "没有 skill" in out

    def test_list_shows_installed(self, user_dir, tmp_path, capsys):
        src = _make_src_skill(tmp_path, "shown", "should be listed")
        main(["skill", "install", str(src)])
        capsys.readouterr()  # 丢掉 install 的输出
        main(["skill", "list"])
        out = capsys.readouterr().out
        assert "shown" in out
        assert "should be listed" in out


class TestInfo:
    def test_info_shows_source(self, user_dir, tmp_path, capsys):
        src = _make_src_skill(tmp_path, "with-info", "test")
        main(["skill", "install", str(src)])
        capsys.readouterr()
        main(["skill", "info", "with-info"])
        out = capsys.readouterr().out
        assert "with-info" in out
        assert "test" in out
        assert "installed from" in out
        assert str(src) in out

    def test_info_missing_skill(self, user_dir):
        with pytest.raises(SystemExit, match="不存在"):
            main(["skill", "info", "nonexistent"])


class TestRemove:
    def test_remove_user_skill(self, user_dir, tmp_path, capsys):
        src = _make_src_skill(tmp_path, "to-remove", "test")
        main(["skill", "install", str(src)])
        capsys.readouterr()
        rc = main(["skill", "remove", "to-remove"])
        assert rc == 0
        assert not (user_dir / "to-remove").exists()

    def test_remove_missing_skill(self, user_dir):
        with pytest.raises(SystemExit, match="不存在"):
            main(["skill", "remove", "nonexistent"])


class TestUpdate:
    def test_update_reuses_source(self, user_dir, tmp_path, capsys):
        src = _make_src_skill(tmp_path, "updatable", "v1")
        main(["skill", "install", str(src)])
        capsys.readouterr()

        # 改源
        (src / "SKILL.md").write_text(
            "---\nname: updatable\ndescription: v2\n---\n\n新版\n",
            encoding="utf-8",
        )

        rc = main(["skill", "update", "updatable"])
        assert rc == 0
        content = (user_dir / "updatable" / "SKILL.md").read_text(encoding="utf-8")
        assert "v2" in content
        assert "新版" in content

    def test_update_without_source_marker(self, user_dir, tmp_path):
        # 手工放一个 skill 不走 install，就没 marker
        d = user_dir / "no-marker"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: no-marker\ndescription: 手工放的\n---\n\nbody\n",
            encoding="utf-8",
        )
        with pytest.raises(SystemExit, match=".install-source"):
            main(["skill", "update", "no-marker"])


class TestCliEntryPoint:
    """基本冒烟：入口能被 python -m 执行。"""

    def test_module_dash_m_works(self):
        result = subprocess.run(
            ["python", "-m", "backend.cli", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "梦蝶 CLI" in result.stdout
