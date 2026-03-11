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
            "请尽可能帮助用户，遇到不确定的事情可以先用工具探索。"
        )
