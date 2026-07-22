import asyncio
from pathlib import Path
from .base import Tool
from .context import ToolContext


class _PathResolver:
    """
    统一的路径解析：绝对路径直接用，相对路径基于 ToolContext.cwd。
    sandbox_mode:
      - "free"      完全放开
      - "project"   相对路径必须落在 cwd 子树下，绝对路径同上
      - "workspace" 兼容旧行为：相对路径必须落在 cwd 子树下（此时 cwd = ./workspace）

    额外允许根（_extra_allowed_roots）：即使 sandbox_mode 是 project/workspace，
    如果路径落在这些根之一下也放行。用于放开 ~/.mengdie/skills/ 这类
    "沙箱外但明确安全"的目录，让 Agent 通过 skill-creator 类 skill 直接
    write_file 到 user skills 目录。
    """

    _extra_allowed_roots: list[Path] = []

    @classmethod
    def add_allowed_root(cls, root: Path) -> None:
        r = Path(root).expanduser().resolve()
        if r not in cls._extra_allowed_roots:
            cls._extra_allowed_roots.append(r)

    @classmethod
    def _is_under_allowed(cls, resolved: Path) -> bool:
        for root in cls._extra_allowed_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    @classmethod
    def resolve(cls, path: str, ctx: ToolContext | None) -> Path:
        p = Path(path).expanduser()
        # 无 ctx 时不做任何限制（用于极少的启动期直接调用）
        if ctx is None:
            return p.resolve() if p.is_absolute() else Path.cwd() / p

        if not p.is_absolute():
            p = ctx.cwd / p

        resolved = p.resolve()

        if ctx.sandbox_mode in ("project", "workspace"):
            root = ctx.cwd.resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                if not cls._is_under_allowed(resolved):
                    raise PermissionError(
                        f"路径 '{path}' 超出当前工作目录 '{root}' 限制（sandbox_mode={ctx.sandbox_mode}）"
                    )
        return resolved


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "读取文本文件内容。path 可为绝对路径或相对当前会话工作目录（cwd）的路径。"
        "支持 offset(1-based) 与 limit 分片读取大文件。"
        "示例：{path:'src/main.py'} 或 {path:'/abs/log.txt', offset:1000, limit:200}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（绝对或相对 cwd）"},
            "offset": {"type": "integer", "description": "起始行号，1-based，可选"},
            "limit": {"type": "integer", "description": "读取行数，可选"},
        },
        "required": ["path"],
    }

    async def execute(self, path: str, offset: int = None, limit: int = None,
                      _ctx: ToolContext | None = None) -> str:
        p = _PathResolver.resolve(path, _ctx)
        text = await asyncio.to_thread(p.read_text, encoding="utf-8")
        lines = text.splitlines(keepends=True)
        if offset:
            lines = lines[offset - 1:]
        if limit:
            lines = lines[:limit]
        return "".join(lines) or "(空文件)"


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "创建或覆盖文本文件（**破坏性、需用户确认**）。写入前应先 read_file 或 list_dir 确认。"
        "参数：path（绝对或相对 cwd）、content（完整新文件内容）。父目录自动创建。"
        "示例：{path:'notes/2026-01.md', content:'# 一月\\n...'}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（绝对或相对 cwd）"},
            "content": {"type": "string", "description": "写入的完整文本内容"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str,
                      _ctx: ToolContext | None = None) -> str:
        p = _PathResolver.resolve(path, _ctx)
        p.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_text, content, encoding="utf-8")
        return f"已写入 {p}（{len(content)} 字符）"


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "对单个文件做**单处精确字符串替换**（需用户确认）。old_string 必须在文件中唯一存在；"
        "建议包含 3-5 行上下文以避免歧义。多处替换用 multi_edit；跨文件补丁用 apply_patch。"
        "示例：{path:'src/api.ts', old_string:'const TIMEOUT = 5000', new_string:'const TIMEOUT = 30000'}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（绝对或相对 cwd）"},
            "old_string": {"type": "string", "description": "要替换的原始文本（须唯一）"},
            "new_string": {"type": "string", "description": "替换后的新文本"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(self, path: str, old_string: str, new_string: str,
                      _ctx: ToolContext | None = None) -> str:
        p = _PathResolver.resolve(path, _ctx)
        content = await asyncio.to_thread(p.read_text, encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return "[错误] 未在文件中找到要替换的文本"
        if count > 1:
            return f"[错误] 找到 {count} 处匹配，需要提供更多上下文使其唯一"
        await asyncio.to_thread(
            p.write_text, content.replace(old_string, new_string, 1), encoding="utf-8",
        )
        return "替换成功"


class ReadSkillTool(Tool):
    name = "read_skill"
    description = (
        "读取技能（Skill）的完整指导内容或其目录下的辅助文件。"
        "用户技能（user tier）优先于同名内置技能（builtin tier）。"
        "默认读 SKILL.md；可选 path 参数读同 skill 目录下的子文件（如 scripts/foo.sh、references/x.md）。"
        "示例：{name:'skill-creator'} 或 {name:'skill-creator', path:'scripts/generate.py'}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名称，与 available_skills 列表中的 name 一致"},
            "path": {
                "type": "string",
                "description": "可选。skill 目录下的相对路径，如 'scripts/foo.sh'。缺省读 SKILL.md",
            },
        },
        "required": ["name"],
    }

    def __init__(self, skills_loader):
        # 通过 SkillsLoader 走 SkillIndex 统一查找，不再硬编码路径
        self._skills = skills_loader

    async def execute(self, name: str, path: str | None = None) -> str:
        info = self._skills.find(name)
        if info is None:
            available = [s.name for s in self._skills.list_all()]
            hint = "、".join(sorted(set(available))) or "无"
            return f"[错误] 技能 '{name}' 不存在。可用技能：{hint}"

        skill_dir = info.directory
        if not path:
            target = info.path  # SKILL.md
        else:
            target = (skill_dir / path).resolve()
            try:
                target.relative_to(skill_dir.resolve())
            except ValueError:
                return f"[错误] path 越出 skill 目录：{path}"
            if not target.exists():
                return f"[错误] skill '{name}' 下没有文件 '{path}'"
            if not target.is_file():
                return f"[错误] '{path}' 不是文件"

        return await asyncio.to_thread(target.read_text, encoding="utf-8")


class ListDirTool(Tool):
    name = "list_dir"
    description = (
        "列出目录内容，返回树形结构。path 为绝对路径或相对当前 cwd（'.' 表示 cwd 本身）。"
        "depth 控制展开层数，默认 2。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "目录路径（绝对或相对 cwd）。'.' 表示 cwd 本身。",
            },
            "depth": {
                "type": "integer",
                "description": "展开层数，默认 2（1 表示仅当前层，3 表示深度三层）",
            },
        },
    }

    async def execute(self, path: str = ".", depth: int = 2,
                      _ctx: ToolContext | None = None) -> str:
        p = _PathResolver.resolve(path, _ctx)
        lines: list[str] = []
        self._render_tree(p, lines, max_depth=max(1, depth), current_depth=0)
        return "\n".join(lines) or "(空目录)"

    def _render_tree(self, p: Path, lines: list[str], max_depth: int, current_depth: int) -> None:
        indent = "  " * current_depth
        try:
            items = sorted(p.iterdir())
        except PermissionError:
            return
        for item in items:
            if item.is_dir():
                lines.append(f"{indent}📁 {item.name}/")
                if current_depth < max_depth - 1:
                    self._render_tree(item, lines, max_depth, current_depth + 1)
            else:
                lines.append(f"{indent}📄 {item.name}")
