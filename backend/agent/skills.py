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
    1. 系统 Skills（system_skills_dir）：随代码发布，启动时同步到 workspace/.skills_cache/，
       Agent 通过 read_skill(name=xxx) 按需读取。
    2. 用户 Skills（user_skills_dir，即 workspace/skills/）：用户自建，
       在 workspace 沙箱内，Agent 同样通过 read_skill(name=xxx) 按需读取，优先级高于系统 Skills。
    """

    def __init__(self, system_skills_dir: Path, user_skills_dir: Path | None = None):
        self.system_dir = system_skills_dir if system_skills_dir and system_skills_dir.exists() else None
        self.user_dir = user_skills_dir  # 不检查存在性，用户随时可创建

    def sync_system_skills(self, workspace: Path) -> None:
        """启动时将系统 Skills 同步到 workspace/.skills_cache/（只拷贝，不可写）。"""
        if not self.system_dir:
            return
        cache_dir = workspace / ".skills_cache"
        cache_dir.mkdir(exist_ok=True)
        for skill_md in self.system_dir.glob("*/SKILL.md"):
            name = skill_md.parent.name
            dst = cache_dir / name / "SKILL.md"
            dst.parent.mkdir(exist_ok=True)
            shutil.copy2(skill_md, dst)

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
        if not self.user_dir or not self.user_dir.exists():
            return []
        skills = []
        for skill_md in sorted(self.user_dir.glob("*/SKILL.md")):
            name = skill_md.parent.name
            info = self._parse_skill(name, skill_md)
            skills.append(info)
        return skills

    def build_skills_summary(self) -> str:
        """
        生成技能摘要，注入 system prompt。
        只含 name 和 description，Agent 通过 read_skill(name=xxx) 按需读取完整内容。
        """
        skills = self.list_system_skills()
        user_skills = self.list_user_skills()

        if not skills and not user_skills:
            return ""

        lines = ["<available_skills>"]
        lines.append(
            "<!-- 需要使用某技能时，调用 read_skill(name=\"技能名称\") 读取完整指导内容，再按指导执行。\n"
            "     用户技能（user）与系统技能（system）同名时，用户技能优先。-->"
        )

        if skills:
            lines.append("  <!-- 系统技能 -->")
            for s in skills:
                lines.append(f'  <skill name="{s.name}" scope="system">{s.description}</skill>')

        if user_skills:
            lines.append("  <!-- 用户技能 -->")
            for s in user_skills:
                lines.append(f'  <skill name="{s.name}" scope="user">{s.description}</skill>')

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
