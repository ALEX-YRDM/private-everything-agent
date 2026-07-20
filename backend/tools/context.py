"""
ToolContext：会话级工具执行上下文。

由 AgentLoop 在每次工具调用前构造，通过 ToolRegistry 以 _ctx 关键字参数注入到工具的 execute()。
工具可选择性地在自己的 execute 签名里声明 `_ctx: ToolContext | None = None` 接收。
"""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolContext:
    cwd: Path
    session_id: str
    sandbox_mode: str = "workspace"
    trusted_paths: list[str] = field(default_factory=list)
    trusted_commands: list[str] = field(default_factory=list)
