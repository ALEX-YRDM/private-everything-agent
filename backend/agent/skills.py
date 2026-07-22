"""
Skills 系统：两层 tier 索引 + mtime 感知缓存。

- Built-in（内置）：./skills/          — 随代码发布，只读
- User（用户）：~/.mengdie/skills/     — 手动装 + Agent 生成，可写

优先级：User > Built-in（同名 skill User 胜出）。

read_skill 通过 SkillIndex 定位（不再依赖 workspace/.skills_cache/），
每个 SKILL.md 走 (path, mtime_ns) 的 lru_cache，用户编辑立刻生效。
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger


SkillTier = Literal["user", "builtin"]

# 用户 skills 默认位置；用 USER_SKILLS_DIR 环境变量可覆盖，方便测试
_USER_SKILLS_DEFAULT = Path.home() / ".mengdie" / "skills"


def get_user_skills_dir() -> Path:
    """返回用户 skills 目录（可通过 USER_SKILLS_DIR 环境变量覆盖）。"""
    env = os.environ.get("USER_SKILLS_DIR")
    return Path(env).expanduser().resolve() if env else _USER_SKILLS_DEFAULT


@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path                            # SKILL.md 的绝对路径
    tier: SkillTier
    when: str = ""                        # 触发说明（frontmatter.when）
    requires_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)
    parse_error: str | None = None        # frontmatter 解析出问题时的原因

    @property
    def directory(self) -> Path:
        return self.path.parent


@lru_cache(maxsize=256)
def _read_skill_frontmatter(path_str: str, mtime_ns: int) -> dict:
    """带 mtime 失效的 frontmatter 读取。返回 {} 或 {'_error': '...'}."""
    try:
        content = Path(path_str).read_text(encoding="utf-8")
    except OSError as e:
        return {"_error": f"read failed: {e}"}
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return {"_error": "missing YAML frontmatter (--- header)"}
    try:
        raw = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        return {"_error": f"YAML parse error: {e}"}
    if not isinstance(raw, dict):
        return {"_error": "frontmatter is not a mapping"}
    return raw


class SkillIndex:
    """两层 skill 索引。核心 API：list()、find(name)、available(info)。"""

    def __init__(self, builtin_dir: Path | None, user_dir: Path | None = None):
        self.builtin_dir = builtin_dir if builtin_dir and builtin_dir.exists() else None
        # user_dir 可能还不存在——用户第一次装 skill 时会创建
        self.user_dir = user_dir or get_user_skills_dir()

    # ── 扫描 ───────────────────────────────────────────────────

    def _scan_tier(self, root: Path | None, tier: SkillTier) -> list[SkillInfo]:
        if not root or not root.exists():
            return []
        skills = []
        for skill_md in sorted(root.glob("*/SKILL.md")):
            info = self._parse(skill_md, tier)
            if info is not None:
                skills.append(info)
        return skills

    def _parse(self, skill_md: Path, tier: SkillTier) -> SkillInfo | None:
        try:
            mtime = skill_md.stat().st_mtime_ns
        except OSError:
            return None
        raw = _read_skill_frontmatter(str(skill_md), mtime)
        err = raw.get("_error") if isinstance(raw, dict) else None
        name = skill_md.parent.name

        description = (raw or {}).get("description")
        # description 是 skill 能被 Agent 正确触发的关键——缺失或退化为 name 都视为坏 skill
        if not err and (not description or str(description).strip() == name):
            err = "description missing or equal to skill name (self-referential)"

        # 兼容旧格式的 nanobot.requires
        nanobot = (raw or {}).get("nanobot") or {}
        requires = (raw or {}).get("requires") or nanobot.get("requires") or {}

        return SkillInfo(
            name=name,
            description=str(description) if description else name,
            path=skill_md,
            tier=tier,
            when=str((raw or {}).get("when") or ""),
            requires_bins=list(requires.get("bins") or []),
            requires_env=list(requires.get("env") or []),
            parse_error=err,
        )

    # ── 查询 ───────────────────────────────────────────────────

    def list(self, include_broken: bool = False) -> list[SkillInfo]:
        """返回所有 skills，User tier 优先（同名覆盖 Builtin）。

        include_broken=True 时返回 parse_error 非空的坏 skill，供前端展示；
        默认过滤掉，避免污染 Agent 视野。
        """
        merged: dict[str, SkillInfo] = {}
        # 先 builtin，后 user——同名 user 覆盖
        for info in self._scan_tier(self.builtin_dir, "builtin"):
            merged[info.name] = info
        for info in self._scan_tier(self.user_dir, "user"):
            merged[info.name] = info
        result = list(merged.values())
        if not include_broken:
            result = [s for s in result if not s.parse_error]
        return sorted(result, key=lambda s: (s.tier != "user", s.name))

    def find(self, name: str) -> SkillInfo | None:
        """按名字查找单个 skill，User 优先。"""
        # 直接扫两个 tier 中该 name 的目录，避免 list() 全量扫
        for root, tier in [(self.user_dir, "user"), (self.builtin_dir, "builtin")]:
            if not root:
                continue
            skill_md = root / name / "SKILL.md"
            if skill_md.exists():
                return self._parse(skill_md, tier)
        return None

    def available(self, info: SkillInfo) -> bool:
        """依赖检查：所有 requires_bins 可解析 + 所有 requires_env 已设置。"""
        for bin_name in info.requires_bins:
            if not shutil.which(bin_name):
                return False
        for env_key in info.requires_env:
            if not os.environ.get(env_key):
                return False
        return True

    def missing(self, info: SkillInfo) -> list[str]:
        """返回缺失的依赖项列表（前端提示用）。"""
        missing = []
        for b in info.requires_bins:
            if not shutil.which(b):
                missing.append(f"bin:{b}")
        for e in info.requires_env:
            if not os.environ.get(e):
                missing.append(f"env:{e}")
        return missing


class SkillsLoader:
    """
    对外接口层。ContextBuilder / API 层与它交互，内部委托 SkillIndex。
    保留 SkillsLoader 命名是为了向后兼容既有引用；内部实现全部换新。
    """

    def __init__(self, builtin_dir: Path, user_dir: Path | None = None):
        self.index = SkillIndex(builtin_dir, user_dir)
        # 暴露给旧调用点方便 refactor
        self.builtin_dir = self.index.builtin_dir
        self.user_dir = self.index.user_dir

    def list_all(self, include_broken: bool = False) -> list[SkillInfo]:
        return self.index.list(include_broken=include_broken)

    def find(self, name: str) -> SkillInfo | None:
        return self.index.find(name)

    def available(self, info: SkillInfo) -> bool:
        return self.index.available(info)

    def missing(self, info: SkillInfo) -> list[str]:
        return self.index.missing(info)

    def build_skills_summary(self) -> str:
        """
        生成技能摘要，注入 system prompt。

        - 只含 name / description / when 提示 / available 标记；
        - 依赖不满足的 skill 不再从摘要过滤，但显式标 available="false"
          让 Agent 明确知道"存在但不能用"；
        - 完整 SKILL.md 由 Agent 通过 read_skill(name=xxx) 按需读取。
        - 头部指明 user skill 存放路径，覆盖任何 skill 内部的路径假设。
        """
        skills = self.index.list()
        if not skills:
            return ""

        user_dir_hint = str(self.user_dir)

        lines = ["<available_skills>"]
        lines.append(
            "<!-- 遇到匹配的用户任务时，先调用 read_skill(name=\"技能名\") 拿完整指导，再按指导执行。\n"
            "     available=\"false\" 表示依赖缺失（缺 bin/env），跳过即可。\n"
            "     scope=\"user\" 是用户自建/安装的技能；scope=\"builtin\" 是内置。\n"
            f"     新建 skill 存放路径：{user_dir_hint}/<skill-name>/SKILL.md -->"
        )
        for s in skills:
            avail = "true" if self.available(s) else "false"
            missing = ",".join(self.missing(s))
            when_frag = f' when="{s.when}"' if s.when else ""
            miss_frag = f' missing="{missing}"' if missing else ""
            lines.append(
                f'  <skill name="{s.name}" scope="{s.tier}" available="{avail}"'
                f'{when_frag}{miss_frag}>{s.description}</skill>'
            )
        lines.append("</available_skills>")
        return "\n".join(lines)

    def invalidate_cache(self) -> None:
        """外部改动 skill 目录（新增/删除/安装）后调用，清 frontmatter 缓存。"""
        _read_skill_frontmatter.cache_clear()
        logger.debug("skill frontmatter cache cleared")

    # ── 生成 / 安装（写路径都落到 user tier） ─────────────────

    _NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

    @classmethod
    def validate_name(cls, name: str) -> str | None:
        """校验 skill name：kebab-case、1-64 字符。返回 None 表示合法。"""
        if not name or not cls._NAME_RE.match(name):
            return "name 必须是 kebab-case（小写字母/数字/连字符），1-64 字符"
        return None

    def create_user_skill(
        self,
        name: str,
        description: str,
        body: str,
        when: str = "",
        requires: dict | None = None,
        overwrite: bool = False,
    ) -> Path:
        """
        在 user tier 创建一个新 skill。

        - 强校验：name kebab-case、description 非空且不等于 name。
        - 禁止覆盖 builtin 同名（防误伤内置能力）；user 同名若 overwrite=False 也拒绝。
        - 自动包装 YAML frontmatter，body 只需要 markdown 正文。
        """
        if err := self.validate_name(name):
            raise ValueError(err)
        description = (description or "").strip()
        if not description:
            raise ValueError("description 不能为空")
        if description == name:
            raise ValueError("description 不能与 name 相同（会导致触发不清晰）")

        # 不允许覆盖 builtin 同名（覆盖是允许的但要用户显式确认，先严格）
        if self.builtin_dir and (self.builtin_dir / name / "SKILL.md").exists():
            raise ValueError(f"内置 skill '{name}' 已存在，请换个名字（不允许覆盖 builtin）")

        target_dir = self.user_dir / name
        target_md = target_dir / "SKILL.md"
        if target_md.exists() and not overwrite:
            raise ValueError(f"user skill '{name}' 已存在（overwrite=True 可覆盖）")

        # 组装 frontmatter
        fm: dict = {"name": name, "description": description}
        if when:
            fm["when"] = when
        if requires:
            requires_clean: dict = {}
            if requires.get("bins"):
                requires_clean["bins"] = list(requires["bins"])
            if requires.get("env"):
                requires_clean["env"] = list(requires["env"])
            if requires_clean:
                fm["requires"] = requires_clean

        target_dir.mkdir(parents=True, exist_ok=True)
        # yaml.safe_dump 默认 sort_keys=True，为可读性关掉
        fm_yaml = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
        target_md.write_text(
            f"---\n{fm_yaml}\n---\n\n{body.strip()}\n",
            encoding="utf-8",
        )
        self.invalidate_cache()
        return target_md

    def install_from_path(self, source: Path, name: str | None = None,
                          overwrite: bool = False) -> Path:
        """
        从本地目录安装 skill 到 user tier。source 必须是包含 SKILL.md 的目录。
        name 缺省用 source 目录名；已存在同名 builtin 会被拒绝。
        """
        source = source.expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"源路径不是目录：{source}")
        if not (source / "SKILL.md").exists():
            raise ValueError(f"源目录缺少 SKILL.md：{source}")

        target_name = name or source.name
        if err := self.validate_name(target_name):
            raise ValueError(err)
        if self.builtin_dir and (self.builtin_dir / target_name / "SKILL.md").exists():
            raise ValueError(f"内置 skill '{target_name}' 已存在，请指定 name 参数换名安装")

        target_dir = self.user_dir / target_name
        if target_dir.exists():
            if not overwrite:
                raise ValueError(f"user skill '{target_name}' 已存在（overwrite=True 可覆盖）")
            shutil.rmtree(target_dir)

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target_dir)
        self.invalidate_cache()
        return target_dir

    def delete_user_skill(self, name: str) -> bool:
        """删除 user tier 下的一个 skill。返回是否真的删了。"""
        if err := self.validate_name(name):
            raise ValueError(err)
        target = self.user_dir / name
        if not target.exists():
            return False
        # 只允许删 user tier，不动 builtin
        shutil.rmtree(target)
        self.invalidate_cache()
        return True
