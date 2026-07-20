"""
项目类型探测：读 package.json / pyproject.toml / git 等，输出结构化项目摘要。

结果由 AgentLoop 缓存到 session_metadata.project_probe，供 ContextBuilder 注入 prompt。
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path


_MAX_READ_BYTES = 20 * 1024


def _read_capped(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:_MAX_READ_BYTES]
    except Exception:
        return None


def _detect_js_framework(deps: dict) -> str | None:
    for k in ("next", "vue", "@vue/cli-service", "svelte", "react", "@angular/core", "remix", "nuxt", "astro"):
        if k in deps:
            v = deps[k]
            v_short = str(v).lstrip("^~>=<")
            if k == "next": return f"Next.js {v_short}"
            if k in ("vue", "@vue/cli-service"): return f"Vue {v_short}"
            if k == "svelte": return f"Svelte {v_short}"
            if k == "react": return f"React {v_short}"
            if k == "@angular/core": return f"Angular {v_short}"
            if k == "remix": return f"Remix {v_short}"
            if k == "nuxt": return f"Nuxt {v_short}"
            if k == "astro": return f"Astro {v_short}"
    return None


def _detect_py_framework(text: str) -> str | None:
    if re.search(r"\bfastapi\b", text, re.IGNORECASE):
        return "FastAPI"
    if re.search(r"\bdjango\b", text, re.IGNORECASE):
        return "Django"
    if re.search(r"\bflask\b", text, re.IGNORECASE):
        return "Flask"
    if re.search(r"\blitestar\b", text, re.IGNORECASE):
        return "Litestar"
    return None


async def _git_info(cwd: Path) -> dict:
    """返回 {branch, dirty}；不是 git 仓库时返回空 dict。"""
    if not (cwd / ".git").exists():
        return {}

    async def _run(*args: str) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args, cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return out.decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    branch = await _run("git", "rev-parse", "--abbrev-ref", "HEAD")
    status = await _run("git", "status", "--porcelain")
    dirty = len(status.splitlines()) if status else 0
    return {"branch": branch or None, "dirty": dirty}


async def probe(cwd: Path) -> dict:
    """
    检测项目类型并返回结构化摘要。缺失字段直接省略。

    返回 dict 键：
      language, framework, package_manager,
      test_cmd, build_cmd, dev_cmd,
      entry_points: list[str],
      git: {branch, dirty}
    """
    cwd = Path(cwd).expanduser().resolve()
    result: dict = {"cwd": str(cwd)}

    # ── JavaScript / TypeScript ──
    pkg_json = cwd / "package.json"
    if pkg_json.exists():
        raw = _read_capped(pkg_json)
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            data = {}
        deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        # 语言：typescript 依赖或 tsconfig 存在 → TS，否则 JS
        is_ts = "typescript" in deps or (cwd / "tsconfig.json").exists()
        result["language"] = "TypeScript" if is_ts else "JavaScript"
        fw = _detect_js_framework(deps)
        if fw:
            result["framework"] = fw
        # 包管理探测
        if (cwd / "pnpm-lock.yaml").exists(): result["package_manager"] = "pnpm"
        elif (cwd / "yarn.lock").exists():    result["package_manager"] = "yarn"
        elif (cwd / "bun.lockb").exists():    result["package_manager"] = "bun"
        elif (cwd / "package-lock.json").exists(): result["package_manager"] = "npm"
        # scripts
        scripts = data.get("scripts") or {}
        pm = result.get("package_manager", "npm")
        if scripts.get("test"): result["test_cmd"] = f"{pm} test"
        if scripts.get("build"): result["build_cmd"] = f"{pm} run build"
        for k in ("dev", "start", "serve"):
            if scripts.get(k):
                result["dev_cmd"] = f"{pm} run {k}" if k != "start" else f"{pm} start"
                break
        # 入口
        entries = []
        for k in ("main", "module", "bin"):
            v = data.get(k)
            if isinstance(v, str): entries.append(v)
            elif isinstance(v, dict): entries.extend(v.values())
        if entries: result["entry_points"] = entries[:5]

    # ── Python ──
    for f in ("pyproject.toml", "requirements.txt", "setup.py"):
        p = cwd / f
        if p.exists():
            text = _read_capped(p) or ""
            result.setdefault("language", "Python")
            fw = _detect_py_framework(text)
            if fw:
                result.setdefault("framework", fw)
            if (cwd / "poetry.lock").exists(): result.setdefault("package_manager", "poetry")
            elif (cwd / "uv.lock").exists():   result.setdefault("package_manager", "uv")
            elif (cwd / "Pipfile").exists():   result.setdefault("package_manager", "pipenv")
            else: result.setdefault("package_manager", "pip")
            # 测试/启动命令启发式：pytest 常见
            if not result.get("test_cmd"):
                if re.search(r"pytest", text, re.IGNORECASE):
                    result["test_cmd"] = "pytest"
            break

    # ── Rust ──
    if (cwd / "Cargo.toml").exists():
        result.setdefault("language", "Rust")
        result.setdefault("package_manager", "cargo")
        result.setdefault("build_cmd", "cargo build")
        result.setdefault("test_cmd", "cargo test")
        result.setdefault("dev_cmd", "cargo run")

    # ── Go ──
    if (cwd / "go.mod").exists():
        result.setdefault("language", "Go")
        result.setdefault("build_cmd", "go build ./...")
        result.setdefault("test_cmd", "go test ./...")

    # ── Java ──
    if (cwd / "pom.xml").exists():
        result.setdefault("language", "Java")
        result.setdefault("package_manager", "maven")
    elif (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
        result.setdefault("language", "Java/Kotlin")
        result.setdefault("package_manager", "gradle")

    # ── Ruby ──
    if (cwd / "Gemfile").exists():
        result.setdefault("language", "Ruby")
        result.setdefault("package_manager", "bundler")

    # ── Makefile 目标 ──
    mk = cwd / "Makefile"
    if mk.exists():
        mk_text = _read_capped(mk) or ""
        for target in ("test", "build", "run", "dev", "start"):
            if re.search(rf"^{target}\s*:", mk_text, re.MULTILINE):
                key = f"{target if target != 'run' else 'dev'}_cmd"
                result.setdefault(key, f"make {target}")

    # ── Git ──
    git = await _git_info(cwd)
    if git:
        result["git"] = git

    return result
