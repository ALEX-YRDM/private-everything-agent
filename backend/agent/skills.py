import time
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
    1. 系统 Skills（system_skills_dir）：随代码发布，启动时增量同步到 workspace/.skills_cache/，
       Agent 通过 read_skill(name=xxx) 按需读取。
    2. 用户 Skills（user_skills_dir，即 workspace/skills/）：用户自建，
       在 workspace 沙箱内，Agent 同样通过 read_skill(name=xxx) 按需读取，优先级高于系统 Skills。
    """

    _CACHE_TTL = 60  # 系统 Skills 列表缓存有效期（秒）

    def __init__(self, system_skills_dir: Path, user_skills_dir: Path | None = None):
        self.system_dir = system_skills_dir if system_skills_dir and system_skills_dir.exists() else None
        self.user_dir = user_skills_dir  # 不检查存在性，用户随时可创建
        self._system_cache: list[SkillInfo] | None = None
        self._system_cache_time: float = 0

    def sync_system_skills(self, workspace: Path) -> None:
        """启动时将系统 Skills 增量同步到 workspace/.skills_cache/（仅更新有变更的文件）。"""
        if not self.system_dir:
            return
        cache_dir = workspace / ".skills_cache"
        cache_dir.mkdir(exist_ok=True)
        for skill_md in self.system_dir.glob("*/SKILL.md"):
            name = skill_md.parent.name
            dst = cache_dir / name / "SKILL.md"
            dst.parent.mkdir(exist_ok=True)
            # 仅当源文件更新时才复制，避免每次启动全量 IO
            if not dst.exists() or skill_md.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(skill_md, dst)

    def list_system_skills(self, filter_unavailable: bool = True) -> list[SkillInfo]:
        """列出所有系统 Skills（带 TTL 缓存，避免每轮 prompt 构建时重复读取文件系统）。"""
        if not self.system_dir:
            return []

        now = time.monotonic()
        if self._system_cache is None or (now - self._system_cache_time) > self._CACHE_TTL:
            self._system_cache = [
                self._parse_skill(p.parent.name, p)
                for p in sorted(self.system_dir.glob("*/SKILL.md"))
            ]
            self._system_cache_time = now

        if filter_unavailable:
            return [s for s in self._system_cache if self._check_requirements(s)]
        return list(self._system_cache)

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

    def invalidate_cache(self) -> None:
        """手动清除系统 Skills 缓存（例如管理员更新了系统 Skills 后调用）。"""
        self._system_cache = None
        self._system_cache_time = 0

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
