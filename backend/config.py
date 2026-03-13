from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Any


class LLMConfig(BaseSettings):
    default_model: str = "gpt-4o"
    api_key: str | None = None
    api_base: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.1
    reasoning_effort: str | None = None
    context_window_tokens: int = 65536
    max_iterations: int = 40

    model_config = {"env_prefix": "LLM__", "extra": "ignore"}


class ToolsConfig(BaseSettings):
    brave_api_key: str | None = None
    restrict_to_workspace: bool = True
    shell_timeout: int = 30

    model_config = {"env_prefix": "TOOLS__", "extra": "ignore"}


class MCPServer(BaseSettings):
    name: str
    transport: str = "stdio"
    command: list[str] | None = None
    url: str | None = None
    env: dict[str, str] = {}

    model_config = {"extra": "ignore"}


class AppConfig(BaseSettings):
    workspace: str = "./workspace"
    config_dir: str = "."          # AGENTS.md / SOUL.md / USER.md 所在目录（不在 agent 可写的 workspace 内）
    skills_dir: str = "./skills"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    mcp_servers: list[MCPServer] = []

    model_config = {"env_file": ".env", "env_nested_delimiter": "__", "extra": "ignore"}
