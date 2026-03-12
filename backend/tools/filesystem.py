from pathlib import Path
from .base import Tool


class _WorkspaceMixin:
    workspace: Path
    restrict: bool

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        resolved = p.resolve()
        if self.restrict and not str(resolved).startswith(str(self.workspace.resolve())):
            raise PermissionError(f"路径 '{path}' 超出 workspace 限制")
        return resolved


class ReadFileTool(_WorkspaceMixin, Tool):
    name = "read_file"
    description = "读取文件内容。支持指定起始行和行数。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "offset": {"type": "integer", "description": "起始行号（1-based，可选）"},
            "limit": {"type": "integer", "description": "读取行数（可选）"},
        },
        "required": ["path"],
    }

    def __init__(self, workspace: Path, restrict_to_workspace: bool = True):
        self.workspace = workspace
        self.restrict = restrict_to_workspace

    async def execute(self, path: str, offset: int = None, limit: int = None) -> str:
        p = self._resolve(path)
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        if offset:
            lines = lines[offset - 1:]
        if limit:
            lines = lines[:limit]
        return "".join(lines) or "(空文件)"


class WriteFileTool(_WorkspaceMixin, Tool):
    name = "write_file"
    description = "写入文件内容（覆盖模式）。父目录不存在时自动创建。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, workspace: Path, restrict_to_workspace: bool = True):
        self.workspace = workspace
        self.restrict = restrict_to_workspace

    async def execute(self, path: str, content: str) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入 {p}（{len(content)} 字符）"


class EditFileTool(_WorkspaceMixin, Tool):
    name = "edit_file"
    description = "精确替换文件中的字符串片段。old_string 必须唯一存在于文件中。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string", "description": "要替换的原始文本"},
            "new_string": {"type": "string", "description": "替换后的新文本"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def __init__(self, workspace: Path, restrict_to_workspace: bool = True):
        self.workspace = workspace
        self.restrict = restrict_to_workspace

    async def execute(self, path: str, old_string: str, new_string: str) -> str:
        p = self._resolve(path)
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


class ListDirTool(_WorkspaceMixin, Tool):
    name = "list_dir"
    description = "列出目录内容，返回文件树形结构。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认为 workspace 根目录"},
        },
    }

    def __init__(self, workspace: Path, restrict_to_workspace: bool = True):
        self.workspace = workspace
        self.restrict = restrict_to_workspace

    async def execute(self, path: str = ".") -> str:
        p = self._resolve(path)
        lines = []
        for item in sorted(p.iterdir()):
            prefix = "📁 " if item.is_dir() else "📄 "
            lines.append(f"{prefix}{item.name}")
        return "\n".join(lines) or "(空目录)"
