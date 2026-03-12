import yaml
import re
import shutil
import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path
    requires_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)


class SkillsLoader:
    """
    Skills 是 SKILL.md 文件（带 YAML frontmatter），教导 Agent 如何完成特定任务。

    两类 Skills：
    1. 系统 Skills（system_skills_dir）：随代码发布，用户可在 UI 中按需启用/禁用，
       启用后以「摘要列表 + 需要时 read_file 懒加载」方式注入 system prompt。
    2. 用户 Skills（user_skills_dir，即 workspace/skills/）：用户自建，
       全部自动注入 system prompt（完整内容）。
    """

    def __init__(self, system_skills_dir: Path, user_skills_dir: Path | None = None):
        self.system_dir = system_skills_dir if system_skills_dir and system_skills_dir.exists() else None
        self.user_dir = user_skills_dir if user_skills_dir and user_skills_dir.exists() else None

    def list_system_skills(self, filter_unavailable: bool = True) -> list[SkillInfo]:
        """列出所有系统 Skills。"""
        if not self.system_dir:
            return []
        skills = []
        for skill_md in sorted(self.system_dir.glob("*/SKILL.md")):
            name = skill_md.parent.name
            info = self._parse_skill(name, skill_md)
            if filter_unavailable and not self._check_requirements(info):
                continue
            skills.append(info)
        return skills

    def list_user_skills(self) -> list[SkillInfo]:
        """列出 workspace/skills/ 中的用户自定义 Skills。"""
        if not self.user_dir:
            return []
        skills = []
        for skill_md in sorted(self.user_dir.glob("*/SKILL.md")):
            name = skill_md.parent.name
            info = self._parse_skill(name, skill_md)
            skills.append(info)
        return skills

    def build_user_skills_summary(self) -> str:
        """
        生成用户技能摘要（懒加载），路径为相对 workspace 的路径，
        模型可直接用 read_file 读取。
        """
        skills = self.list_user_skills()
        if not skills:
            return ""
        lines = ["<user_skills>"]
        lines.append("<!-- 你的自定义技能。需要使用时，用 read_file 读取对应 path（相对工作目录）的完整内容。-->")
        for s in skills:
            # 路径相对于 workspace（即 user_dir 的上级目录）
            try:
                rel_path = s.path.relative_to(self.user_dir.parent)
            except ValueError:
                rel_path = s.path
            lines.append(f'  <skill name="{s.name}" path="{rel_path}">{s.description}</skill>')
        lines.append("</user_skills>")
        return "\n".join(lines)

    def build_skills_summary(self, enabled_names: set[str] | None = None) -> str:
        """
        生成 XML 格式的系统技能摘要，注入 system prompt。
        - enabled_names=None 表示全部启用。
        - Agent 需要使用某技能时，用 read_file 工具读取对应路径的完整 SKILL.md。
        """
        all_skills = self.list_system_skills()
        if enabled_names is not None:
            skills = [s for s in all_skills if s.name in enabled_names]
        else:
            skills = all_skills

        if not skills:
            return ""

        # 取第一个技能的绝对路径作为示例
        example_path = str(skills[0].path) if skills else ""
        lines = ["<available_skills>"]
        lines.append(
            "<!-- 系统技能使用说明：\n"
            "     每个 skill 的 path 属性是绝对路径，直接传给 read_file 即可读取完整内容。\n"
            f'     示例：read_file(path="{example_path}")\n'
            "     ⚠️ 不要在 workspace 里搜索，skill 文件不在工作目录中。-->"
        )
        for s in skills:
            lines.append(f'  <skill name="{s.name}" path="{s.path}">{s.description}</skill>')
        lines.append("</available_skills>")
        return "\n".join(lines)

    def _parse_skill(self, name: str, path: Path) -> SkillInfo:
        content = path.read_text(encoding="utf-8")
        raw: dict = {}
        match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if match:
            try:
                raw = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                pass
        nanobot = raw.get("nanobot", {}) or {}
        description = raw.get("description") or nanobot.get("description") or name
        requires = nanobot.get("requires") or raw.get("requires") or {}
        return SkillInfo(
            name=name,
            description=description,
            path=path,
            requires_bins=requires.get("bins", []),
            requires_env=requires.get("env", []),
        )

    def _check_requirements(self, skill: SkillInfo) -> bool:
        for bin_name in (skill.requires_bins or []):
            if not shutil.which(bin_name):
                return False
        for env_key in (skill.requires_env or []):
            if not os.environ.get(env_key):
                return False
        return True
