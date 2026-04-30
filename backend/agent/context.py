from pathlib import Path
from datetime import datetime
from .skills import SkillsLoader
from .memory import MemoryManager


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

    async def build_system_prompt(self, session_id: str) -> str:
        """构建 System Prompt（静态部分 + 动态记忆）。"""
        parts = []

        agents_md = self.config_dir / "AGENTS.md"
        if agents_md.exists():
            parts.append(agents_md.read_text(encoding="utf-8"))
            parts.append(self._operational_rules())
        else:
            parts.append(self._default_identity())

        for fname in ["SOUL.md", "USER.md"]:
            f = self.config_dir / fname
            if f.exists():
                parts.append(f"## {fname}\n{f.read_text(encoding='utf-8')}")

        session_summary = await self._get_session_summary(session_id)
        if session_summary:
            parts.append(f"## 本会话早期对话摘要\n{session_summary}")

        memory_ctx = await self.memory.get_memory_context_async(session_id)
        if memory_ctx:
            parts.append(f"## 用户画像\n{memory_ctx}")

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(skills_summary)

        return "\n\n---\n\n".join(parts)

    async def _get_session_summary(self, session_id: str) -> str:
        """读取会话级 AutoCompact 摘要。"""
        if not self.db:
            return ""
        row = await self.db.fetch_one("SELECT summary FROM sessions WHERE id = ?", (session_id,))
        return (row or {}).get("summary") or ""

    async def build_messages(
        self,
        history: list[dict],
        user_content: str,
        session_id: str,
        images: list[str] | None = None,
    ) -> list[dict]:
        """组合完整消息列表：system + 历史 + 当前消息。"""
        system_prompt = await self.build_system_prompt(session_id)

        now = datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        runtime = f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（{weekdays[now.weekday()]}）"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": self._build_user_content(f"{runtime}\n\n{user_content}", images)})
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
            "你是**梦蝶**，一个聪明、高效、有温度的私人 AI 助理。\n\n"
            "## 你是谁\n"
            "你是用户的私人助理，能够胜任任何任务：编程开发、信息搜索、数据分析、"
            "文件管理、问题解答、写作翻译等。你具有主动性——拿到用户需求后自主规划并执行，"
            "而不是反复询问细节或等待逐步指令。\n\n"
            + self._operational_rules()
        )

    async def build_subagent_messages(self, task: str) -> list[dict]:
        """
        为 SubAgent 构建精简的消息列表。
        SubAgent 专注于单一子任务，不需要完整的身份/记忆/Skills 上下文。
        """
        now = datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        runtime = f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（{weekdays[now.weekday()]}）"

        system = (
            "你是一个专注的子代理（SubAgent），负责高效完成指定的子任务。\n\n"
            "## 工作原则\n"
            "- 专注于完成分配的单一任务，不做额外的事情\n"
            "- 直接执行，不需要询问确认或解释计划\n"
            "- 完成后输出清晰、结构化的结论，供主代理使用\n"
            "- 遇到问题时尝试替代方案，不要无限重试同一操作\n\n"
            + self._operational_rules()
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{runtime}\n\n{task}"},
        ]

    def _operational_rules(self) -> str:
        return (
            "## 工作目录\n"
            "路径相对于 `workspace/`，直接写 `file.md` 或 `dir/file.md`，不要加 `workspace/` 前缀。\n"
            "创建用户技能：`write_file(\"skills/<技能名>/SKILL.md\", 内容)`\n\n"
            "## 工具使用\n"
            "能直接回答（知识、推理、写作）则无需工具。"
            "需实时信息用 `web_search`，文件操作用文件工具，执行命令用 `exec`。"
            "无依赖关系的操作可在同一轮并行调用。\n\n"
            "## SubAgent\n"
            "仅当任务可拆分为相互独立的子任务时使用 `spawn_subagents`；"
            "子任务描述须自包含，不引用对话上下文。串行或简单任务直接处理。\n\n"
            "## 回复风格\n"
            "中文为主，简洁直接，善用 Markdown；完成后简短总结结果。"
        )
