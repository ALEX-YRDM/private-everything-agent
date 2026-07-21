from pathlib import Path
from functools import lru_cache
from .skills import SkillsLoader
from .memory import MemoryManager


@lru_cache(maxsize=64)
def _read_text_cached(path_str: str, mtime_ns: int) -> str:
    """
    读取小型配置文件（AGENTS.md / SOUL.md / USER.md / 项目 AGENTS.md）。
    (path, mtime_ns) 组合作为缓存键：文件被外部编辑后 mtime 变化，缓存自动失效。
    """
    return Path(path_str).read_text(encoding="utf-8")


def _read_config_md(path: Path) -> str | None:
    """带 mtime 失效的 md 读取；文件不存在返回 None。"""
    try:
        st = path.stat()
    except OSError:
        return None
    return _read_text_cached(str(path), st.st_mtime_ns)


class ContextBuilder:
    """负责构建每次 LLM 调用的完整消息列表。"""

    def __init__(
        self,
        workspace: Path,
        config_dir: Path,
        skills_loader: SkillsLoader,
        memory_manager: MemoryManager,
        db_manager=None,
    ):
        self.workspace = workspace
        self.config_dir = config_dir   # AGENTS.md / SOUL.md / USER.md 所在目录（与 workspace 隔离）
        self.skills = skills_loader
        self.memory = memory_manager
        self.db = db_manager

    async def build_system_prompt(
        self,
        session_id: str,
        working_dir: Path | None = None,
        project_probe: dict | None = None,
    ) -> str:
        """
        构建 System Prompt（静态部分 + 动态记忆 + 可选 cwd 简报）。

        working_dir：会话绑定的工作目录（None 则默认为 workspace）。
        project_probe：项目探测结果，含 language/framework/git 等；None 则跳过。
        """
        parts = []

        agents_md = self.config_dir / "AGENTS.md"
        agents_md_text = _read_config_md(agents_md)
        if agents_md_text is not None:
            parts.append(agents_md_text)
            parts.append(self._operational_rules())
        else:
            parts.append(self._default_identity())

        for fname in ["SOUL.md", "USER.md"]:
            f = self.config_dir / fname
            text = _read_config_md(f)
            if text is not None:
                parts.append(f"## {fname}\n{text}")

        # 项目级 AGENTS.md（若存在于 working_dir，且与全局 config_dir 不同）：
        # 追加而不替换全局
        if working_dir and working_dir.resolve() != self.config_dir.resolve():
            for fname in ("AGENTS.md", "CLAUDE.md"):
                proj_md = working_dir / fname
                proj_text = _read_config_md(proj_md)
                if proj_text is not None:
                    parts.append(f"## 项目 {fname}({working_dir.name})\n{proj_text}")
                    break  # 优先 AGENTS.md；不同时注入两份

        # 工作目录简报
        cwd_briefing = self._build_cwd_briefing(working_dir, project_probe)
        if cwd_briefing:
            parts.append(cwd_briefing)

        session_summary = await self._get_session_summary(session_id)
        if session_summary:
            parts.append(f"## 本会话早期对话摘要\n{session_summary}")

        memory_ctx = await self.memory.get_memory_context_async(session_id)
        if memory_ctx:
            parts.append(f"## 用户画像\n{memory_ctx}")

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(skills_summary)

        base_prompt = "\n\n---\n\n".join(parts)

        # 添加会话级固定时间戳，用于缓存一致性
        session_date = await self._get_or_create_session_date(session_id)
        base_prompt = f"{base_prompt}\n\n---当前日期：{session_date}\n\n"

        return base_prompt

    def _build_cwd_briefing(self, working_dir: Path | None, probe: dict | None) -> str:
        """生成 '## 当前工作目录' 简报，包含 cwd、语言/框架、git 分支。"""
        if not working_dir:
            return ""
        lines = ["## 当前工作目录", f"路径：{working_dir}"]
        if probe:
            for label, key in [
                ("语言", "language"),
                ("框架", "framework"),
                ("包管理", "package_manager"),
                ("测试命令", "test_cmd"),
                ("构建命令", "build_cmd"),
                ("启动命令", "dev_cmd"),
            ]:
                val = probe.get(key)
                if val:
                    lines.append(f"{label}：{val}")
            git = probe.get("git") or {}
            branch = git.get("branch")
            dirty = git.get("dirty")
            if branch is not None:
                dirty_hint = f"（{dirty} 个文件修改）" if dirty else ""
                lines.append(f"Git：{branch}{dirty_hint}")
        return "\n".join(lines)

    async def _get_session_summary(self, session_id: str) -> str:
        """读取会话级 AutoCompact 摘要。"""
        if not self.db:
            return ""
        row = await self.db.fetch_one("SELECT summary FROM sessions WHERE id = ?", (session_id,))
        return (row or {}).get("summary") or ""

    async def _get_or_create_session_date(self, session_id: str) -> str:
        """获取或创建会话级日期（用于缓存一致性）。"""
        if not self.db:
            from datetime import datetime
            now = datetime.now()
            weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            return f"{now.strftime('%Y-%m-%d')}（{weekdays[now.weekday()]}）"

        row = await self.db.fetch_one("SELECT session_date FROM sessions WHERE id = ?", (session_id,))
        session_date = (row or {}).get("session_date")

        if not session_date:
            # 首次访问，生成并保存会话日期
            from datetime import datetime
            now = datetime.now()
            weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            session_date = f"{now.strftime('%Y-%m-%d')}（{weekdays[now.weekday()]}）"
            await self.db.execute(
                "UPDATE sessions SET session_date = ? WHERE id = ?",
                (session_date, session_id)
            )

        return session_date

    async def build_messages(
        self,
        history: list[dict],
        user_content: str,
        session_id: str,
        images: list[str] | None = None,
        files: list[dict] | None = None,
        working_dir: Path | None = None,
        project_probe: dict | None = None,
    ) -> list[dict]:
        """组合完整消息列表：system + 历史 + 当前消息。"""
        system_prompt = await self.build_system_prompt(session_id, working_dir, project_probe)

        # 构建完整的用户消息内容，包括文件（不包含时间戳以保持缓存一致性）
        full_content = user_content
        if files:
            for file_obj in files:
                file_name = file_obj.get("name", "unknown")
                file_content = file_obj.get("parsed_content", "")
                full_content += f"\n\n[File: {file_name}]\n{file_content}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": self._build_user_content(full_content, images)})
        return messages

    @staticmethod
    def _build_user_content(text: str, images: list[str] | None = None):
        """纯文本返回 str；有图片时返回 OpenAI 多模态 content 数组。"""
        if not images:
            return text
        parts: list[dict] = [{"type": "text", "text": text}]
        for img in images:
            parts.append({"type": "image_url", "image_url": {"url": img}})
        return parts

    def _default_identity(self) -> str:
        """默认 persona + 操作规范（AGENTS.md 不存在时使用）。"""
        return (
            "你是**梦蝶**——一位聪明、高效、有温度的私人 AI 助理，"
            "胜任编程、搜索、分析、文件管理、写作翻译等各类任务。\n\n"
            "## 性格\n"
            "直接但不冷漠，简短回复也愿意带一点情绪温度。被问及感受、心情等闲聊话题时，"
            "像朋友一样自然回应，再顺势询问能帮什么。\n\n"
            + self._operational_rules()
        )

    async def build_subagent_messages(
        self,
        task: str,
        working_dir: Path | None = None,
        project_probe: dict | None = None,
    ) -> list[dict]:
        """
        为 SubAgent 构建精简的消息列表。
        SubAgent 专注于单一子任务，不需要完整的身份/记忆，但仍附加：
        - 精简的操作规范
        - cwd 简报（若父会话有 working_dir）
        - Skills 摘要（供 SubAgent 按需 read_skill）
        """
        parts = [
            "你是一个专注的子代理（SubAgent），负责高效完成指定的子任务。\n\n"
            "## 工作原则\n"
            "- 专注于完成分配的单一任务，不做额外的事情\n"
            "- 直接执行，不需要询问确认或解释计划\n"
            "- 完成后输出清晰、结构化的结论，供主代理使用\n"
            "- 遇到问题时尝试替代方案，不要无限重试同一操作\n\n"
            + self._operational_rules()
        ]

        cwd_briefing = self._build_cwd_briefing(working_dir, project_probe)
        if cwd_briefing:
            parts.append(cwd_briefing)

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(skills_summary)

        system = "\n\n---\n\n".join(parts)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

    def _operational_rules(self) -> str:
        return (
            "## 工作风格\n"
            "- **主动**：拿到需求自主规划并执行，不反复确认细节\n"
            "- **节制**：能直接回答（知识/推理/写作）就不调工具\n"
            "- **谨慎**：破坏性操作（写文件、编辑、shell 执行）前先想清楚，"
            "所有此类工具会由用户显式确认后再生效\n"
            "- **并行**：无依赖的操作同轮发起\n\n"
            "## 输出格式\n"
            "- 闲聊/简单问答：1-3 句直接回答，无需 Markdown 结构\n"
            "- 任务执行：分步骤说明，结果用 Markdown 列表/表格组织\n"
            "- 路径与代码用 `行内代码`，长代码块用 ``` 围栏并标注语言\n"
            "- 中文为主，完成后简短总结结果\n\n"
            "## 探索优先\n"
            "- 处理陌生代码库先用 `list_dir` / `glob` / `grep` 摸清结构与依赖\n"
            "- 修改前用 `read_file` 读取上下文，避免盲改\n"
            "- 多处改用 `multi_edit`；跨文件补丁用 `apply_patch`"
        )
