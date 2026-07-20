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
    """

    @staticmethod
    def resolve(path: str, ctx: ToolContext | None) -> Path:
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
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
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
        p.write_text(content, encoding="utf-8")
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
        content = p.read_text(encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return "[错误] 未在文件中找到要替换的文本"
        if count > 1:
            return f"[错误] 找到 {count} 处匹配，需要提供更多上下文使其唯一"
        p.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
        return "替换成功"


class ReadSkillTool(Tool):
    name = "read_skill"
    description = "读取技能（Skill）的完整指导内容。用户技能优先于同名系统技能。"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名称，与 available_skills 列表中的 name 一致"},
        },
        "required": ["name"],
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.cache_dir = workspace / ".skills_cache"
        self.user_skills_dir = workspace / "skills"

    async def execute(self, name: str) -> str:
        # 用户技能优先
        user_path = self.user_skills_dir / name / "SKILL.md"
        if user_path.exists():
            return user_path.read_text(encoding="utf-8")

        # 系统技能缓存
        cache_path = self.cache_dir / name / "SKILL.md"
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        available: list[str] = []
        if self.cache_dir.exists():
            available += [d.name for d in self.cache_dir.iterdir() if d.is_dir()]
        if self.user_skills_dir.exists():
            available += [d.name for d in self.user_skills_dir.iterdir() if d.is_dir()]
        hint = "、".join(sorted(set(available))) or "无"
        return f"[错误] 技能 '{name}' 不存在。可用技能：{hint}"


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
