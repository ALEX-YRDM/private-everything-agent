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
    always: bool = False
    requires_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)


class SkillsLoader:
    """
    Skills 是 SKILL.md 文件（带 YAML frontmatter），教导 Agent 如何完成特定任务。

    目录优先级（高 → 低）：
    1. ./skills/  （用户自定义，可覆盖内置）
    2. ./builtin_skills/ （内置技能，随代码发布）
    """

    def __init__(self, user_skills_dir: Path, builtin_skills_dir: Path | None = None):
        self.dirs = [d for d in [user_skills_dir, builtin_skills_dir] if d and d.exists()]

    def list_skills(self, filter_unavailable: bool = True) -> list[SkillInfo]:
        seen: set[str] = set()
        skills = []
        for d in self.dirs:
            for skill_md in sorted(d.glob("*/SKILL.md")):
                name = skill_md.parent.name
                if name in seen:
                    continue
                seen.add(name)
                info = self._parse_skill(name, skill_md)
                if filter_unavailable and not self._check_requirements(info):
                    continue
                skills.append(info)
        return skills

    def get_always_skills(self) -> str:
        """返回标记 always=true 的技能的完整内容（直接注入 system prompt）。"""
        parts = []
        for skill in self.list_skills():
            if skill.always:
                content = skill.path.read_text(encoding="utf-8")
                content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
                parts.append(f"## Skill: {skill.name}\n{content}")
        return "\n\n".join(parts)

    def build_skills_summary(self) -> str:
        """
        生成 XML 格式的技能摘要，注入 system prompt。
        Agent 需要时用 read_file 工具读取完整 SKILL.md。
        """
        skills = [s for s in self.list_skills() if not s.always]
        if not skills:
            return ""
        lines = ["<available_skills>"]
        lines.append("<!-- 以下是可用的专项技能。需要使用某技能时，先用 read_file 读取完整内容。-->")
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
        # 兼容两种格式：
        # 格式1：顶层 description + nanobot.always/requires（设计文档格式）
        # 格式2：顶层扁平化（description/always/requires 都在顶层）
        nanobot = raw.get("nanobot", {}) or {}
        description = raw.get("description") or nanobot.get("description") or name
        requires = nanobot.get("requires") or raw.get("requires") or {}
        return SkillInfo(
            name=name,
            description=description,
            path=path,
            always=nanobot.get("always", raw.get("always", False)),
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
