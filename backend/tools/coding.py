"""
编码专用工具集：glob / grep / multi_edit / apply_patch。

所有工具通过 _ctx: ToolContext 拿到 cwd 与 sandbox_mode。
gitignore 过滤依赖 pathspec；apply_patch 依赖 unidiff。
"""
from __future__ import annotations

import asyncio
import fnmatch
import re
import subprocess
import shutil
from pathlib import Path

from .base import Tool
from .context import ToolContext
from .filesystem import _PathResolver


# ── gitignore 加载（缓存到 cwd 首次访问） ─────────────────────────────────

_GITIGNORE_CACHE: dict[str, object] = {}


def _load_gitignore(root: Path):
    """尝试为 root 加载 .gitignore，返回 pathspec.PathSpec 或 None。"""
    key = str(root)
    if key in _GITIGNORE_CACHE:
        return _GITIGNORE_CACHE[key]
    gi = root / ".gitignore"
    spec = None
    if gi.exists():
        try:
            import pathspec as _ps
            spec = _ps.PathSpec.from_lines("gitwildmatch", gi.read_text().splitlines())
        except Exception:
            spec = None
    _GITIGNORE_CACHE[key] = spec
    return spec


def _is_ignored(spec, root: Path, path: Path) -> bool:
    """判断某路径是否被 gitignore 忽略；.git/ 默认忽略。"""
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        return False
    if rel == ".git" or rel.startswith(".git/") or "/.git/" in rel:
        return True
    if spec is None:
        return False
    return spec.match_file(rel + ("/" if path.is_dir() else ""))


# ── GlobTool ─────────────────────────────────────────────────────────────

class GlobTool(Tool):
    name = "glob"
    description = (
        "按 glob 模式在工作目录下查找文件，返回按 mtime 降序的路径列表。"
        "默认应用 .gitignore 过滤。示例：{pattern:'**/*.py'} 查找所有 Python 文件；"
        "{pattern:'src/**/*.ts', limit:200}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "glob 模式（如 '**/*.py'、'src/**/*.ts'）"},
            "path": {"type": "string", "description": "起始目录（相对 cwd 或绝对路径），默认为 cwd"},
            "limit": {"type": "integer", "description": "最多返回条数，默认 200"},
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, path: str = ".", limit: int = 200,
                      _ctx: ToolContext | None = None) -> str:
        base = _PathResolver.resolve(path, _ctx)
        if not base.exists() or not base.is_dir():
            return f"[错误] 起始目录不存在或不是目录: {base}"

        root = (_ctx.cwd if _ctx else base).resolve()
        spec = _load_gitignore(root)
        matches: list[Path] = []
        for p in base.rglob(pattern):
            if _is_ignored(spec, root, p):
                continue
            matches.append(p)

        matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        truncated = len(matches) > limit
        matches = matches[:limit]

        lines = []
        for m in matches:
            try:
                lines.append(str(m.relative_to(root)))
            except ValueError:
                lines.append(str(m))
        header = f"共 {len(matches)} 项" + ("（已截断，还有更多）" if truncated else "")
        return f"{header}\n" + "\n".join(lines) if lines else "(无匹配)"


# ── GrepTool ─────────────────────────────────────────────────────────────

class GrepTool(Tool):
    name = "grep"
    description = (
        "在工作目录中按正则搜索文件内容。"
        "output_mode: content（每行匹配 path:lineno:text）| files_with_matches（仅文件列表）| count（每文件匹配数）。"
        "默认应用 .gitignore 过滤。检测到 ripgrep（rg）时优先使用，否则回退 Python 遍历。"
        "示例：{pattern:'def handle_.*', path:'backend', output_mode:'content'}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "正则表达式（Python re 语法）"},
            "path": {"type": "string", "description": "搜索起点（相对 cwd 或绝对路径），默认 cwd"},
            "include": {"type": "string", "description": "文件名 glob 过滤，如 '*.py'（可选）"},
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_with_matches", "count"],
                "description": "输出格式，默认 content",
            },
            "context_lines": {"type": "integer", "description": "content 模式的上下文行数，默认 0"},
            "case_insensitive": {"type": "boolean", "description": "忽略大小写，默认 false"},
            "limit": {"type": "integer", "description": "最大结果行数，默认 300"},
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, path: str = ".", include: str = None,
                      output_mode: str = "content", context_lines: int = 0,
                      case_insensitive: bool = False, limit: int = 300,
                      _ctx: ToolContext | None = None) -> str:
        base = _PathResolver.resolve(path, _ctx)
        if not base.exists():
            return f"[错误] 路径不存在: {base}"

        root = (_ctx.cwd if _ctx else base).resolve()
        if shutil.which("rg"):
            return await self._grep_rg(pattern, base, root, include, output_mode,
                                        context_lines, case_insensitive, limit)
        # 纯 Python 后备：整体丢到线程池，避免大目录遍历阻塞 event loop
        return await asyncio.to_thread(
            self._grep_python, pattern, base, include, output_mode,
            context_lines, case_insensitive, limit, root,
        )

    async def _grep_rg(self, pattern: str, base: Path, root: Path, include: str | None,
                       output_mode: str, ctx_lines: int, ci: bool, limit: int) -> str:
        cmd = ["rg", "--color=never", "--no-heading"]
        if ci:
            cmd.append("-i")
        if include:
            cmd += ["-g", include]
        if output_mode == "files_with_matches":
            cmd.append("-l")
        elif output_mode == "count":
            cmd.append("-c")
        else:
            if ctx_lines:
                cmd += ["-C", str(ctx_lines)]
            cmd += ["-n"]  # 显示行号
        cmd += [pattern, str(base)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode not in (0, 1):
            return f"[rg 错误] {stderr.decode('utf-8', errors='replace')[:400]}"
        raw = stdout.decode("utf-8", errors="replace")
        # 把绝对路径替换成相对 root 的路径
        raw = raw.replace(str(root) + "/", "")
        lines = raw.splitlines()
        truncated = len(lines) > limit
        return "\n".join(lines[:limit]) + ("\n...[已截断]" if truncated else "") \
            or "(无匹配)"

    def _grep_python(self, pattern: str, base: Path, include: str | None,
                     output_mode: str, ctx_lines: int, ci: bool, limit: int,
                     gitignore_root: Path) -> str:
        flags = re.IGNORECASE if ci else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"[错误] 无效正则: {e}"

        spec = _load_gitignore(gitignore_root)
        results: list[str] = []
        counts: dict[str, int] = {}
        files_with: list[str] = []

        iterator = base.rglob("*") if base.is_dir() else iter([base])
        for f in iterator:
            if not f.is_file():
                continue
            if _is_ignored(spec, gitignore_root, f):
                continue
            if include and not fnmatch.fnmatch(f.name, include):
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except (PermissionError, OSError):
                continue

            for i, line in enumerate(lines, start=1):
                if regex.search(line):
                    if output_mode == "files_with_matches":
                        rel = str(f.relative_to(gitignore_root))
                        if rel not in files_with:
                            files_with.append(rel)
                        break
                    elif output_mode == "count":
                        counts[str(f.relative_to(gitignore_root))] = \
                            counts.get(str(f.relative_to(gitignore_root)), 0) + 1
                    else:
                        rel = str(f.relative_to(gitignore_root))
                        start = max(1, i - ctx_lines)
                        end = min(len(lines), i + ctx_lines)
                        for j in range(start, end + 1):
                            prefix = f"{rel}:{j}:"
                            marker = "" if j == i else "-"
                            results.append(f"{prefix}{marker}{lines[j-1]}")
                        if len(results) >= limit:
                            break
            if output_mode == "content" and len(results) >= limit:
                break

        if output_mode == "files_with_matches":
            return "\n".join(files_with) or "(无匹配文件)"
        if output_mode == "count":
            return "\n".join(f"{p}: {c}" for p, c in counts.items()) or "(无匹配)"
        truncated = len(results) > limit
        return "\n".join(results[:limit]) + ("\n...[已截断]" if truncated else "") \
            or "(无匹配)"


# ── MultiEditTool ────────────────────────────────────────────────────────

class MultiEditTool(Tool):
    name = "multi_edit"
    description = (
        "在**同一文件**中做多处精确字符串替换（**需用户确认**）。"
        "所有 edit 顺序应用，任一失败整体回滚；replace_all=false 时 old_string 必须唯一。"
        "示例：{path:'src/api.ts', edits:[{old_string:'v1', new_string:'v2'}, ...]}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（绝对或相对 cwd）"},
            "edits": {
                "type": "array",
                "description": "替换列表，按顺序应用",
                "items": {
                    "type": "object",
                    "properties": {
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                        "replace_all": {"type": "boolean", "description": "默认 false，仅替换首个匹配且要求唯一"},
                    },
                    "required": ["old_string", "new_string"],
                },
                "minItems": 1,
            },
        },
        "required": ["path", "edits"],
    }

    async def execute(self, path: str, edits: list[dict],
                      _ctx: ToolContext | None = None) -> str:
        p = _PathResolver.resolve(path, _ctx)
        if not p.exists():
            return f"[错误] 文件不存在: {p}"

        original = await asyncio.to_thread(p.read_text, encoding="utf-8")
        working = original
        applied = []

        for idx, e in enumerate(edits, start=1):
            old = e["old_string"]
            new = e["new_string"]
            replace_all = bool(e.get("replace_all", False))
            count = working.count(old)
            if count == 0:
                return (
                    f"[回滚] 第 {idx} 处 old_string 未找到，全部编辑已放弃。\n"
                    f"未找到片段前 80 字符：{old[:80]!r}"
                )
            if not replace_all and count > 1:
                return (
                    f"[回滚] 第 {idx} 处 old_string 匹配 {count} 次但 replace_all=false。\n"
                    f"请补充上下文使其唯一，或设置 replace_all=true。"
                )
            if replace_all:
                working = working.replace(old, new)
            else:
                working = working.replace(old, new, 1)
            applied.append(f"  {idx}. {'全部替换 %d 处' % count if replace_all else '单处替换'}")

        await asyncio.to_thread(p.write_text, working, encoding="utf-8")
        orig_lines = original.count("\n") + 1
        new_lines = working.count("\n") + 1
        return (
            f"已应用 {len(edits)} 处编辑到 {p}\n"
            + "\n".join(applied)
            + f"\n行数变化：{orig_lines} → {new_lines}"
        )


# ── ApplyPatchTool ───────────────────────────────────────────────────────

class ApplyPatchTool(Tool):
    name = "apply_patch"
    description = (
        "应用统一 diff 格式的补丁到多个文件（**需用户确认**）。"
        "适合跨文件的批量修改；每个 hunk 通过 dry-run 校验后原子写入，任一失败整体拒绝。"
        "补丁需符合 unified diff 规范（--- a/xxx / +++ b/xxx / @@ ... @@）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "patch": {"type": "string", "description": "统一 diff 格式的补丁字符串"},
        },
        "required": ["patch"],
    }

    async def execute(self, patch: str, _ctx: ToolContext | None = None) -> str:
        try:
            from unidiff import PatchSet
        except ImportError:
            return "[错误] 未安装 unidiff，无法解析补丁"

        try:
            patch_set = PatchSet(patch)
        except Exception as e:
            return f"[错误] 补丁解析失败: {e}"

        if not patch_set:
            return "[错误] 补丁为空或格式非法"

        # dry-run：逐文件加载 → 应用 hunk → 收集新内容
        plan: list[tuple[Path, str, str]] = []  # (path, new_content, description)
        for patched_file in patch_set:
            target_rel = patched_file.target_file or patched_file.source_file or ""
            for prefix in ("b/", "a/"):
                if target_rel.startswith(prefix):
                    target_rel = target_rel[len(prefix):]
                    break
            target_path = _PathResolver.resolve(target_rel, _ctx)

            if patched_file.is_added_file:
                # 新增文件：直接拼合 + 号行
                new_lines = []
                for hunk in patched_file:
                    for line in hunk:
                        if line.is_added or line.is_context:
                            new_lines.append(line.value)
                new_content = "".join(new_lines)
                plan.append((target_path, new_content, f"新增 {target_rel}"))
                continue

            if patched_file.is_removed_file:
                plan.append((target_path, None, f"删除 {target_rel}"))
                continue

            if not target_path.exists():
                return f"[错误] 目标文件不存在: {target_path}"
            original_lines = (
                await asyncio.to_thread(target_path.read_text, encoding="utf-8")
            ).splitlines(keepends=True)
            new_lines = list(original_lines)

            # 从后往前应用 hunk 避免行号偏移
            offset = 0
            for hunk in patched_file:
                start = hunk.source_start - 1 + offset
                length = hunk.source_length

                # 校验上下文
                expected_ctx_lines = [line.value for line in hunk if line.is_context or line.is_removed]
                actual = new_lines[start : start + length]
                if [l.rstrip("\r\n") for l in expected_ctx_lines] != [l.rstrip("\r\n") for l in actual]:
                    return (
                        f"[冲突] {target_rel} 第 {hunk.source_start} 行附近上下文不匹配。\n"
                        f"补丁期望:\n{''.join(expected_ctx_lines)[:400]}\n"
                        f"实际内容:\n{''.join(actual)[:400]}"
                    )

                replacement = [line.value for line in hunk if line.is_context or line.is_added]
                new_lines[start : start + length] = replacement
                offset += len(replacement) - length

            plan.append((target_path, "".join(new_lines), f"修改 {target_rel}"))

        # 全部通过 → 原子应用
        for target, content, _desc in plan:
            if content is None:
                if target.exists():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(target.write_text, content, encoding="utf-8")

        summary = "\n".join(f"  - {desc}" for _, _, desc in plan)
        return f"已应用补丁（{len(plan)} 个文件）：\n{summary}"
