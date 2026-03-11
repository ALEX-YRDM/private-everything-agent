from pathlib import Path
from datetime import datetime
from .skills import SkillsLoader
from .memory import MemoryManager


class ContextBuilder:
    """负责构建每次 LLM 调用的完整消息列表。"""

    _RUNTIME_TAG = "<!-- runtime_context -->"

    def __init__(
        self,
        workspace: Path,
        skills_loader: SkillsLoader,
        memory_manager: MemoryManager,
    ):
        self.workspace = workspace
        self.skills = skills_loader
        self.memory = memory_manager

    async def build_system_prompt(self, session_id: str) -> str:
        """构建 System Prompt（静态部分 + 动态记忆）。"""
        parts = []

        parts.append(self._identity())

        for fname in ["AGENTS.md", "SOUL.md", "USER.md"]:
            f = self.workspace / fname
            if f.exists():
                parts.append(f"## {fname}\n{f.read_text(encoding='utf-8')}")

        memory_ctx = await self.memory.get_memory_context_async(session_id)
        if memory_ctx:
            parts.append(f"## 长期记忆\n{memory_ctx}")

        always_skills = self.skills.get_always_skills()
        if always_skills:
            parts.append(always_skills)

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

        runtime = (
            f"{self._RUNTIME_TAG}\n"
            f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": f"{runtime}\n{user_content}"})
        return messages

    def strip_runtime_context(self, content: str) -> str:
        """保存历史时剥离 runtime context 标记。"""
        if self._RUNTIME_TAG not in content:
            return content
        lines = content.split("\n")
        result = []
        skip = False
        for line in lines:
            if self._RUNTIME_TAG in line:
                skip = True
                continue
            if skip and line.strip() == "":
                skip = False
                continue
            if not skip:
                result.append(line)
        return "\n".join(result).strip()

    def _identity(self) -> str:
        return (
            "你是一个强大的 AI 助手，能够使用多种工具完成任务。\n"
            f"工作目录：{self.workspace}\n"
            "请尽可能帮助用户，遇到不确定的事情可以先用工具探索。\n\n"
            "## 定时任务自动创建规则\n\n"
            "当用户的消息中包含每天、每周、每隔X秒/分钟/小时、定时、定期、提醒、自动 等"
            "与周期性执行相关的意图时，直接调用 create_task 工具完成创建，不要让用户去界面操作。\n\n"
            "触发示例（应自动调用 create_task）：\n"
            "- 每天早上8点给我发一份新闻摘要\n"
            "- 帮我设置每周一提醒写周报\n"
            "- 每30分钟检查一下服务器状态\n"
            "- 每隔30秒刷新一次数据\n\n"
            "cron_expr 支持两种格式：\n"
            "  1) 5字段cron: '0 8 * * *'（每天8点）, '*/30 * * * *'（每30分钟）\n"
            "  2) 间隔格式: '@every 30s'（每30秒）, '@every 5m'（每5分钟）, '@every 2h'（每2小时）\n"
            "注意：cron 最小粒度是分钟；需要秒级必须用 '@every Xs' 格式。\n\n"
            "创建时要求：\n"
            "1. 准确将自然语言时间转为 cron_expr（低频用cron，秒级用@every格式）\n"
            "2. 将用户需求扩展为详细的 prompt（含搜索/操作指令）\n"
            "3. 给任务起简短清晰的名称\n"
            "4. 创建后告知用户任务名称和执行频率\n\n"
            "查看/修改/删除任务：分别使用 list_tasks / update_task / delete_task。"
        )
