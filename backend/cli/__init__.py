"""
mengdie CLI: 独立操作 user tier 的 skill 目录。

不依赖后端进程在跑——通过环境变量或默认位置直接找到 ~/.mengdie/skills/。
后端进程若已在运行，因 mtime 感知会自动看到新装的 skill。

命令：
    mengdie skill install <source> [--name NAME] [--force]
    mengdie skill list
    mengdie skill info <name>
    mengdie skill remove <name>
    mengdie skill update <name>

<source> 支持：
    - Git URL：https://... / git@...:... / ssh://...git
    - 本地路径：/abs/path 或 ./relative/path

安装完的 skill 目录内会保留一个 .install-source 文件，记录源，
供 `update` 命令重拉。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 复用后端已有逻辑，避免重复实现路径校验 / copytree / frontmatter 解析
from backend.agent.skills import SkillsLoader, get_user_skills_dir


INSTALL_SOURCE_FILE = ".install-source"


# ─────────────────────────── 帮助 ─────────────────────────────────

def _make_loader() -> SkillsLoader:
    """构造只针对 user tier 的 loader（builtin 目录传 None，不参与本 CLI 逻辑）。"""
    user_dir = get_user_skills_dir()
    user_dir.mkdir(parents=True, exist_ok=True)
    return SkillsLoader(builtin_dir=None, user_dir=user_dir)


def _looks_like_git_url(s: str) -> bool:
    """粗判是否是 git URL。太严会误伤 SSH 简写；太宽会把本地路径当成 URL。"""
    if s.startswith(("http://", "https://", "ssh://", "git://")):
        return True
    # SSH 简写：git@host:path 或 host:path.git
    if "@" in s and ":" in s and not s.startswith("/"):
        return True
    if s.endswith(".git"):
        return True
    return False


def _basename_from_url(url: str) -> str:
    """从 URL 推断目录名。https://x/foo/my-skill.git → my-skill"""
    trimmed = url.rstrip("/")
    if trimmed.endswith(".git"):
        trimmed = trimmed[:-4]
    return trimmed.rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def _write_source_marker(target: Path, source: str) -> None:
    """在装好的 skill 目录里写一个源标记，供 update 用。"""
    try:
        (target / INSTALL_SOURCE_FILE).write_text(source + "\n", encoding="utf-8")
    except OSError:
        pass  # 装成功了没写标记也无所谓，只是 update 会不认识


def _read_source_marker(name: str, loader: SkillsLoader) -> str | None:
    marker = loader.user_dir / name / INSTALL_SOURCE_FILE
    if marker.exists():
        try:
            return marker.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return None


# ─────────────────────────── 命令实现 ─────────────────────────────

def _clone_git(url: str, dst: Path, timeout: int = 60) -> None:
    """git clone --depth=1，clone 后剥掉 .git。"""
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", url, str(dst)],
            check=True, capture_output=True, timeout=timeout,
        )
    except FileNotFoundError:
        raise SystemExit("错误：未找到 git 可执行文件，请先装 git")
    except subprocess.TimeoutExpired:
        raise SystemExit(f"错误：git clone 超时（{timeout} 秒）")
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode("utf-8", errors="replace").strip()[:500]
        raise SystemExit(f"错误：git clone 失败\n{stderr or '（无错误输出）'}")

    # 剥 .git（不做版本追踪，避免误导用户以为可以 git pull）
    import shutil
    git_dir = dst / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, ignore_errors=True)


def cmd_install(args) -> int:
    import tempfile
    loader = _make_loader()

    if _looks_like_git_url(args.source):
        preferred = args.name or _basename_from_url(args.source)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_target = Path(tmp) / preferred
            print(f"→ clone {args.source} …")
            _clone_git(args.source, tmp_target)
            try:
                target = loader.install_from_path(
                    tmp_target, name=preferred, overwrite=args.force,
                )
            except ValueError as e:
                raise SystemExit(f"错误：{e}")
        _write_source_marker(target, args.source)
        print(f"✔ 已装到 {target}")
        return 0

    # 本地路径
    src = Path(args.source).expanduser().resolve()
    try:
        target = loader.install_from_path(src, name=args.name, overwrite=args.force)
    except ValueError as e:
        raise SystemExit(f"错误：{e}")
    _write_source_marker(target, str(src))
    print(f"✔ 已装到 {target}")
    return 0


def cmd_list(args) -> int:
    loader = _make_loader()
    skills = [s for s in loader.list_all(include_broken=True) if s.tier == "user"]
    if not skills:
        print(f"（{loader.user_dir} 下没有 skill）")
        return 0

    for s in skills:
        tags = []
        if s.parse_error:
            tags.append(f"broken: {s.parse_error}")
        elif not loader.available(s):
            tags.append(f"missing: {','.join(loader.missing(s))}")
        tag_str = f"  [{'; '.join(tags)}]" if tags else ""
        print(f"  {s.name:24}  {s.description}{tag_str}")
    return 0


def cmd_info(args) -> int:
    loader = _make_loader()
    info = loader.find(args.name)
    if info is None:
        raise SystemExit(f"skill '{args.name}' 不存在")

    print(f"name:        {info.name}")
    print(f"description: {info.description}")
    print(f"tier:        {info.tier}")
    print(f"path:        {info.path}")
    if info.when:
        print(f"when:        {info.when}")
    if info.requires_bins:
        print(f"requires bins: {', '.join(info.requires_bins)}")
    if info.requires_env:
        print(f"requires env:  {', '.join(info.requires_env)}")
    missing = loader.missing(info)
    if missing:
        print(f"missing:     {', '.join(missing)}")
    src = _read_source_marker(info.name, loader)
    if src:
        print(f"installed from: {src}")
    if info.parse_error:
        print(f"parse error: {info.parse_error}")
    return 0


def cmd_remove(args) -> int:
    loader = _make_loader()
    info = loader.find(args.name)
    if info is None:
        raise SystemExit(f"skill '{args.name}' 不存在")
    if info.tier != "user":
        raise SystemExit(f"skill '{args.name}' 是 {info.tier} tier，不能通过 CLI 删除")
    loader.delete_user_skill(args.name)
    print(f"✔ 已删除 {args.name}")
    return 0


def cmd_update(args) -> int:
    import tempfile
    loader = _make_loader()
    info = loader.find(args.name)
    if info is None or info.tier != "user":
        raise SystemExit(f"user skill '{args.name}' 不存在")

    source = _read_source_marker(args.name, loader)
    if not source:
        raise SystemExit(
            f"skill '{args.name}' 没有记录源（.install-source 缺失），"
            f"请手动 install 覆盖：mengdie skill install <url> --force"
        )

    if _looks_like_git_url(source):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_target = Path(tmp) / args.name
            print(f"→ 从 {source} 重新拉取 …")
            _clone_git(source, tmp_target)
            try:
                target = loader.install_from_path(
                    tmp_target, name=args.name, overwrite=True,
                )
            except ValueError as e:
                raise SystemExit(f"错误：{e}")
        _write_source_marker(target, source)
        print(f"✔ 已更新 {target}")
        return 0

    # 本地源：重新 copy
    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"原源路径不存在：{src}")
    try:
        target = loader.install_from_path(src, name=args.name, overwrite=True)
    except ValueError as e:
        raise SystemExit(f"错误：{e}")
    _write_source_marker(target, str(src))
    print(f"✔ 已更新 {target}")
    return 0


# ─────────────────────────── 入口 ─────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mengdie", description="梦蝶 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # skill 子命令组
    p_skill = subparsers.add_parser("skill", help="管理 user tier 的 skills")
    skill_sub = p_skill.add_subparsers(dest="skill_command", required=True)

    p_install = skill_sub.add_parser("install", help="从 URL / 本地路径安装 skill")
    p_install.add_argument("source", help="Git URL 或本地目录路径")
    p_install.add_argument("--name", help="覆盖默认目录名")
    p_install.add_argument("--force", action="store_true", help="覆盖已有同名 user skill")
    p_install.set_defaults(func=cmd_install)

    p_list = skill_sub.add_parser("list", help="列出所有 user skills")
    p_list.set_defaults(func=cmd_list)

    p_info = skill_sub.add_parser("info", help="显示单个 skill 的详细信息")
    p_info.add_argument("name")
    p_info.set_defaults(func=cmd_info)

    p_remove = skill_sub.add_parser("remove", help="删除 user tier 下的 skill")
    p_remove.add_argument("name")
    p_remove.set_defaults(func=cmd_remove)

    p_update = skill_sub.add_parser("update", help="从记录的原源重新拉取")
    p_update.add_argument("name")
    p_update.set_defaults(func=cmd_update)

    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
