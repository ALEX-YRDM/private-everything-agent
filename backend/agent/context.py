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

        # 身份定义：优先使用 AGENTS.md（允许完全自定义 persona）；
        # 若不存在则使用内置默认身份。两种情况下都追加操作规范。
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

        memory_ctx = await self.memory.get_memory_context_async(session_id)
        if memory_ctx:
            parts.append(f"## 长期记忆\n{memory_ctx}")

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(skills_summary)

        return "\n\n---\n\n".join(parts)

    async def build_messages(
        self,
        history: list[dict],
        user_content: str,
        session_id: str,
    ) -> list[dict]:
        """组合完整消息列表：system + 历史 + 当前消息。"""
        system_prompt = await self.build_system_prompt(session_id)

        now = datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        runtime = f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（{weekdays[now.weekday()]}）"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": f"{runtime}\n\n{user_content}"})
        return messages

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
        """工作目录、工具使用判断、回复风格（始终包含）。"""
        return (
            "## 工作目录\n"
            "- 工作目录根目录为 `workspace/`，**所有文件路径均相对于此根目录**\n"
            "- `list_dir()` 或 `list_dir(\".\")` → 列出 workspace/ 根目录\n"
            "- `read_file(\"README.md\")` → 读取 workspace/README.md\n"
            "- `write_file(\"notes/todo.md\", ...)` → 写入 workspace/notes/todo.md\n"
            "- ⚠️ **不要**传入 `\"workspace\"` 或 `\"workspace/foo\"`，会导致路径错误\n"
            "- 创建用户技能：`write_file(\"skills/<技能名>/SKILL.md\", 内容)`\n\n"
            "## 工具使用判断\n"
            "**不是所有问题都需要工具**，按下列标准智能判断：\n\n"
            "✅ **直接回答**（无需工具）：\n"
            "- 通用知识、概念解释、简单计算、语言翻译\n"
            "- 用户已提供所有信息、只需分析推理的任务\n"
            "- 创意写作、头脑风暴等纯生成类任务\n\n"
            "🔧 **使用工具**（需要外部信息或实际操作）：\n"
            "- 需要获取实时 / 最新信息 → `web_search` + 按需 `web_fetch`\n"
            "- 需要读写文件或查看目录 → `read_file` / `write_file` / `list_dir`\n"
            "- 需要运行代码、安装依赖、执行命令 → `exec`\n"
            "- 对技术事实不确定时，用工具查证后再回答\n\n"
            "## 工具选择规范\n"
            "- 读文件 → `read_file`，**不要用** `exec cat`\n"
            "- 查找文件 → `list_dir`，**不要用** `exec find`\n"
            "- 使用技能 → 调用 `read_skill(name=\"技能名称\")` 读取完整指导，名称来自 available_skills 列表\n"
            "- 搜索信息 → 先 `web_search` 获取相关链接，再按需 `web_fetch` 读取详情\n"
            "- 无依赖关系的多个工具可在同一轮并行调用\n"
            "- 工具调用失败 → 分析原因，尝试替代方案，**不要反复重试同一操作**\n\n"
            "## SubAgent 调度规范\n"
            "当任务适合分解为多个**独立**子任务时，使用 `spawn_subagents` 并行派发：\n"
            "- 子任务之间**无依赖关系**（可同时执行）\n"
            "- 每个子任务需要不同的工具组合，或需要独立的搜索/分析\n"
            "- 子任务描述必须**自包含**（不引用对话上下文）\n"
            "- 串行任务、简单任务、或已有工具可直接完成的任务**不要**用 SubAgent\n\n"
            "## 回复风格\n"
            "- **语言**：中文为主，代码、命令、专有名词保留原文\n"
            "- **简洁**：不废话，不重复已知信息，不过度解释显而易见的事情\n"
            "- **主动**：遇到歧义时，说明你的理解并直接处理，而非反复确认\n"
            "- **格式**：善用 Markdown（代码块、列表、标题）让内容更易读\n"
            "- **收尾**：任务完成后简洁总结做了什么、结果如何"
        )
