# Agent 系统技术设计方案

> 基于对 nanobot 源码的深度分析，为本地运行的个人 Agent 系统量身定制。
> 目标：Python 后端 + Vue 3 前端，支持流式输出、MCP 工具、上下文记忆、会话管理。

---

## 一、项目整体架构

### 1.1 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI + asyncio | 原生异步，支持 WebSocket 流式输出 |
| LLM 接入 | LiteLLM | 统一接口，一套代码对接所有主流模型 |
| 数据存储 | SQLite + aiosqlite | 零依赖，本地运行，异步读写 |
| MCP 客户端 | mcp (官方 SDK) | 支持 stdio / SSE / streamableHttp |
| 前端框架 | Vue 3 + Vite | Composition API，轻量快速 |
| 前端状态 | Pinia | Vue 官方状态管理 |
| 前端 UI | Naive UI | 企业级组件库，无需配置即美观 |
| 通信协议 | WebSocket | 流式 token 推送；REST 用于配置类接口 |
| 配置管理 | Pydantic Settings | 类型安全，支持 .env 文件 |

### 1.2 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                   Vue 3 Frontend                     │
│  ┌──────────┐ ┌───────────┐ ┌────────────────────┐  │
│  │ ChatPanel│ │SessionList│ │ SettingsPanel       │  │
│  └──────────┘ └───────────┘ └────────────────────┘  │
│         WebSocket (streaming) + REST API             │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                FastAPI Backend                       │
│  ┌─────────────────────────────────────────────┐    │
│  │              API Layer                       │    │
│  │  /ws/{session_id}  /api/sessions  /api/...  │    │
│  └───────────────────┬─────────────────────────┘    │
│                      │                               │
│  ┌───────────────────▼─────────────────────────┐    │
│  │              Agent Core                      │    │
│  │  AgentLoop → ContextBuilder → MemoryManager  │    │
│  │           ↕              ↕                   │    │
│  │      ToolRegistry    SkillsLoader            │    │
│  └───────────────────┬─────────────────────────┘    │
│                      │                               │
│  ┌───────────────────▼─────────────────────────┐    │
│  │           LLM Provider (LiteLLM)             │    │
│  │  OpenAI / Anthropic / DeepSeek / Gemini /    │    │
│  │  Ollama / 通义千问 / Kimi / 智谱 / ...        │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │            Tools & MCP                       │    │
│  │  filesystem / shell / web_search / web_fetch │    │
│  │  MCP Client (stdio/SSE/http)                 │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │         Session & Memory (SQLite)            │    │
│  │  sessions / messages / memory_store          │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
my-agent/
├── backend/
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置 (Pydantic Settings + .env)
│   ├── database.py                # SQLite 连接、表初始化
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── loop.py                # AgentLoop：核心 ReAct 循环
│   │   ├── context.py             # ContextBuilder：构建完整 Prompt
│   │   ├── memory.py              # MemoryManager：双层记忆 + 整合
│   │   └── skills.py              # SkillsLoader：Skills 加载器
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                # LLMProvider 抽象基类 + LLMResponse
│   │   └── litellm_provider.py    # LiteLLM 统一实现（含流式）
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                # Tool 抽象基类
│   │   ├── registry.py            # ToolRegistry 注册表
│   │   ├── filesystem.py          # read_file / write_file / edit_file / list_dir
│   │   ├── shell.py               # exec（Shell 命令执行）
│   │   ├── web.py                 # web_search / web_fetch
│   │   └── mcp_client.py          # MCP 协议客户端 + 工具包装
│   │
│   ├── session/
│   │   ├── __init__.py
│   │   └── manager.py             # SessionManager（SQLite 持久化）
│   │
│   └── api/
│       ├── __init__.py
│       ├── routes.py              # REST 路由（会话/配置/模型列表）
│       └── websocket.py           # WebSocket 处理（消息收发 + 流式输出）
│
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── components/
│       │   ├── ChatPanel.vue      # 主聊天区域
│       │   ├── MessageBubble.vue  # 单条消息气泡（含 Markdown 渲染）
│       │   ├── ToolCallCard.vue   # 工具调用可视化卡片
│       │   ├── ThinkingBlock.vue  # LLM 推理过程折叠块
│       │   ├── SessionList.vue    # 左侧会话列表
│       │   └── SettingsPanel.vue  # 模型/工具/MCP 配置面板
│       ├── stores/
│       │   ├── chat.ts            # 聊天状态 (Pinia)
│       │   └── settings.ts        # 配置状态 (Pinia)
│       ├── api/
│       │   ├── http.ts            # REST API 封装
│       │   └── websocket.ts       # WebSocket 客户端封装
│       └── utils/
│           └── markdown.ts        # marked + highlight.js
│
├── skills/                        # 用户自定义 Skills 目录
│   └── example-skill/
│       └── SKILL.md
│
├── workspace/                     # Agent 工作目录（文件操作的根目录）
│
├── pyproject.toml                 # Python 依赖
├── .env.example                   # 环境变量模板
└── README.md
```

---

## 三、数据库设计（SQLite）

### 3.1 Schema

```sql
-- 会话表
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,          -- UUID
    title       TEXT NOT NULL DEFAULT '新会话',
    model       TEXT,                      -- 覆盖默认模型
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata    JSON DEFAULT '{}'
);

-- 消息表（对话历史）
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,         -- user / assistant / tool / system
    content         TEXT,                  -- 文本内容
    tool_calls      JSON,                  -- 工具调用列表（仅 role=assistant 时有值）
    tool_call_id    TEXT,                  -- 工具结果关联 ID（仅 role=tool 时有值）
    tool_name       TEXT,                  -- 工具名称（仅 role=tool 时有值）
    reasoning       TEXT,                  -- 思维链内容（DeepSeek/Kimi 等）
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_consolidated INTEGER DEFAULT 0      -- 是否已整合进记忆（0/1）
);

-- 记忆表（长期记忆）
CREATE TABLE IF NOT EXISTS memory_store (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
    memory_md   TEXT DEFAULT '',           -- 结构化记忆（用户偏好、重要事实）
    history_md  TEXT DEFAULT '',           -- 时间线日志
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
```

### 3.2 数据访问封装（database.py）

```python
# database.py
import aiosqlite
from pathlib import Path

DB_PATH = Path("./data/agent.db")

async def get_db() -> aiosqlite.Connection:
    """FastAPI 依赖注入用，返回异步 SQLite 连接。"""
    ...

async def init_db():
    """应用启动时初始化表结构。"""
    ...
```

---

## 四、配置系统（config.py）

```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Any

class LLMConfig(BaseSettings):
    default_model: str = "gpt-4o"
    api_key: str | None = None
    api_base: str | None = None        # 自定义 endpoint
    max_tokens: int = 4096
    temperature: float = 0.1
    reasoning_effort: str | None = None  # "low" / "medium" / "high"（o1/o3 系列）
    context_window_tokens: int = 65536   # 触发记忆整合的 token 阈值
    max_iterations: int = 40            # ReAct 最大循环次数

class ToolsConfig(BaseSettings):
    brave_api_key: str | None = None    # web_search 需要
    restrict_to_workspace: bool = True  # 文件操作是否限制在 workspace 内
    shell_timeout: int = 30             # shell 命令超时秒数

class MCPServer(BaseSettings):
    name: str
    transport: str                      # "stdio" / "sse" / "streamable_http"
    command: list[str] | None = None   # stdio 模式：命令 + 参数
    url: str | None = None             # sse/http 模式：服务地址
    env: dict[str, str] = {}

class AppConfig(BaseSettings):
    workspace: str = "./workspace"
    skills_dir: str = "./skills"
    llm: LLMConfig = LLMConfig()
    tools: ToolsConfig = ToolsConfig()
    mcp_servers: list[MCPServer] = []
    
    model_config = {"env_file": ".env", "env_nested_delimiter": "__"}
```

`.env.example` 示例：
```env
LLM__DEFAULT_MODEL=gpt-4o
LLM__API_KEY=sk-xxx
LLM__API_BASE=                          # 留空使用官方 endpoint
LLM__MAX_TOKENS=4096
LLM__TEMPERATURE=0.1
LLM__CONTEXT_WINDOW_TOKENS=65536

TOOLS__BRAVE_API_KEY=BSA-xxx
TOOLS__RESTRICT_TO_WORKSPACE=true

WORKSPACE=./workspace
SKILLS_DIR=./skills
```

---

## 五、LLM 提供商层

### 5.1 抽象基类（providers/base.py）

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"       # "stop" / "tool_calls" / "error" / "length"
    reasoning_content: str | None = None   # 思维链（DeepSeek R1 / Qwen QwQ 等）

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

# 流式事件类型
@dataclass
class StreamEvent:
    type: str      # "thinking" / "content_delta" / "tool_call" / "tool_result" / "done" / "error"
    content: str | None = None
    data: dict | None = None   # tool_call 时携带 name/args

class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict], **kwargs) -> LLMResponse:
        """非流式调用，返回完整响应。"""
        ...

    @abstractmethod
    async def chat_stream(self, messages: list[dict], tools: list[dict], **kwargs):
        """流式调用，异步生成器，yield StreamEvent。"""
        ...

    async def chat_with_retry(self, messages, tools, max_retries=3, **kwargs) -> LLMResponse:
        """带指数退避重试（应对 429/503）。"""
        import asyncio
        for attempt in range(max_retries):
            try:
                return await self.chat(messages, tools, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if any(code in str(e) for code in ["429", "503", "rate_limit", "overloaded"]):
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
```

### 5.2 LiteLLM 实现（providers/litellm_provider.py）

```python
import litellm
import json
from .base import LLMProvider, LLMResponse, StreamEvent, ToolCallRequest

# 关闭 litellm 的详细日志
litellm.set_verbose = False

class LiteLLMProvider(LLMProvider):
    """
    通过 LiteLLM 统一接入所有主流 LLM。
    
    支持的模型格式示例：
      - "gpt-4o"                       → OpenAI
      - "claude-3-5-sonnet-20241022"   → Anthropic
      - "deepseek/deepseek-chat"       → DeepSeek
      - "gemini/gemini-2.0-flash"      → Google
      - "ollama/qwen2.5:14b"           → 本地 Ollama
      - "openrouter/anthropic/claude-3.5-sonnet" → OpenRouter
    """

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base

    def _build_kwargs(self, model: str, **kwargs) -> dict:
        kw = {"model": model, **kwargs}
        if self.api_key:
            kw["api_key"] = self.api_key
        if self.api_base:
            kw["api_base"] = self.api_base
        return kw

    async def chat(self, messages, tools=None, model="gpt-4o", **kwargs) -> LLMResponse:
        kw = self._build_kwargs(model, messages=messages, **kwargs)
        if tools:
            kw["tools"] = tools
        
        response = await litellm.acompletion(**kw)
        return self._parse_response(response)

    async def chat_stream(self, messages, tools=None, model="gpt-4o", **kwargs):
        """
        流式生成 StreamEvent。
        注意：当有工具调用时，LiteLLM 会在 finish_reason=tool_calls 时
        一次性返回完整工具调用，而不是逐 token 流式。
        """
        kw = self._build_kwargs(model, messages=messages, stream=True, **kwargs)
        if tools:
            kw["tools"] = tools

        accumulated_tool_calls = {}   # index → {id, name, arguments}
        accumulated_content = ""

        async for chunk in await litellm.acompletion(**kw):
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # 流式文本 token
            if delta.content:
                accumulated_content += delta.content
                yield StreamEvent(type="content_delta", content=delta.content)

            # 工具调用增量（LiteLLM 流式下分片返回）
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": tc_delta.function.name or "",
                            "arguments": ""
                        }
                    if tc_delta.id:
                        accumulated_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function.name:
                        accumulated_tool_calls[idx]["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        accumulated_tool_calls[idx]["arguments"] += tc_delta.function.arguments

            # 结束
            if finish_reason == "tool_calls":
                tool_calls = []
                for tc in accumulated_tool_calls.values():
                    try:
                        args = json.loads(tc["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(ToolCallRequest(
                        id=tc["id"], name=tc["name"], arguments=args
                    ))
                    yield StreamEvent(type="tool_call", data={
                        "id": tc["id"], "name": tc["name"], "args": args
                    })
                # 通知 loop 有工具调用需要处理
                yield StreamEvent(type="tool_calls_ready", data={
                    "content": accumulated_content,
                    "tool_calls": [{"id": t.id, "name": t.name, "arguments": t.arguments}
                                   for t in tool_calls]
                })
            elif finish_reason == "stop":
                yield StreamEvent(type="done", content=accumulated_content)

    def _parse_response(self, response) -> LLMResponse:
        msg = response.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCallRequest(
                    id=tc.id, name=tc.function.name, arguments=args
                ))
        reasoning = getattr(msg, "reasoning_content", None)
        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
            reasoning_content=reasoning,
        )

    def get_default_model(self) -> str:
        return "gpt-4o"
```

### 5.3 常见模型接入速查

```python
# 在 .env 中设置对应的 API Key，模型名称直接传给 LiteLLM

SUPPORTED_MODELS = {
    # === OpenAI ===
    "gpt-4o":                        {"env": "OPENAI_API_KEY"},
    "gpt-4o-mini":                   {"env": "OPENAI_API_KEY"},
    "o1":                            {"env": "OPENAI_API_KEY"},
    "o3-mini":                       {"env": "OPENAI_API_KEY"},

    # === Anthropic ===
    "claude-3-5-sonnet-20241022":    {"env": "ANTHROPIC_API_KEY"},
    "claude-3-7-sonnet-20250219":    {"env": "ANTHROPIC_API_KEY"},
    "claude-opus-4-5":               {"env": "ANTHROPIC_API_KEY"},

    # === DeepSeek ===
    "deepseek/deepseek-chat":        {"env": "DEEPSEEK_API_KEY"},
    "deepseek/deepseek-reasoner":    {"env": "DEEPSEEK_API_KEY"},

    # === Google Gemini ===
    "gemini/gemini-2.0-flash":       {"env": "GEMINI_API_KEY"},
    "gemini/gemini-2.5-pro":         {"env": "GEMINI_API_KEY"},

    # === 国内模型 ===
    "dashscope/qwen-max":            {"env": "DASHSCOPE_API_KEY"},      # 通义千问
    "moonshot/moonshot-v1-128k":     {"env": "MOONSHOT_API_KEY"},       # Kimi
    "zhipuai/glm-4":                 {"env": "ZHIPUAI_API_KEY"},        # 智谱
    "volcengine/doubao-pro-32k":     {"env": "VOLCENGINE_API_KEY"},     # 豆包

    # === 本地模型 ===
    "ollama/qwen2.5:14b":            {"env": None, "api_base": "http://localhost:11434"},
    "ollama/llama3.3:70b":           {"env": None, "api_base": "http://localhost:11434"},

    # === 路由网关 ===
    "openrouter/anthropic/claude-3.5-sonnet": {"env": "OPENROUTER_API_KEY"},
    "openrouter/google/gemini-2.0-flash":     {"env": "OPENROUTER_API_KEY"},
}
```

---

## 六、工具系统

### 6.1 工具抽象基类（tools/base.py）

```python
from abc import ABC, abstractmethod
import jsonschema

class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """返回 JSON Schema 格式的参数定义。"""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具，返回字符串结果（供 LLM 读取）。"""
        ...

    def to_schema(self) -> dict:
        """转为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def validate_params(self, params: dict) -> list[str]:
        """返回验证错误列表（空表示合法）。"""
        try:
            jsonschema.validate(params, self.parameters)
            return []
        except jsonschema.ValidationError as e:
            return [str(e.message)]
```

### 6.2 工具注册表（tools/registry.py）

```python
import traceback
from .base import Tool

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict]:
        """返回所有工具的 function calling schema。"""
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"[错误] 工具 '{name}' 不存在"
        errors = tool.validate_params(params)
        if errors:
            return f"[参数错误] {'; '.join(errors)}"
        try:
            result = await tool.execute(**params)
            # 截断超长结果（防止 context 爆炸）
            if len(result) > 10000:
                result = result[:10000] + f"\n...[结果已截断，共 {len(result)} 字符]"
            return result
        except Exception as e:
            return f"[执行错误] {type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}"

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
```

### 6.3 内置工具实现

#### tools/filesystem.py
```python
import os
from pathlib import Path
from .base import Tool

class ReadFileTool(Tool):
    name = "read_file"
    description = "读取文件内容。支持指定起始行和行数。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "offset": {"type": "integer", "description": "起始行号（1-based，可选）"},
            "limit": {"type": "integer", "description": "读取行数（可选）"},
        },
        "required": ["path"]
    }
    
    def __init__(self, workspace: Path, restrict_to_workspace: bool = True):
        self.workspace = workspace
        self.restrict = restrict_to_workspace

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        if self.restrict and not str(p.resolve()).startswith(str(self.workspace.resolve())):
            raise PermissionError(f"路径 '{path}' 超出 workspace 限制")
        return p

    async def execute(self, path: str, offset: int = None, limit: int = None) -> str:
        p = self._resolve(path)
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        if offset:
            lines = lines[offset - 1:]
        if limit:
            lines = lines[:limit]
        return "".join(lines) or "(空文件)"

class WriteFileTool(Tool):
    name = "write_file"
    description = "写入文件内容（覆盖模式）。父目录不存在时自动创建。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"]
    }
    
    def __init__(self, workspace: Path, restrict_to_workspace: bool = True):
        self.workspace = workspace
        self.restrict = restrict_to_workspace

    async def execute(self, path: str, content: str) -> str:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入 {p}（{len(content)} 字符）"

class EditFileTool(Tool):
    name = "edit_file"
    description = "精确替换文件中的字符串片段。old_string 必须唯一存在于文件中。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string", "description": "要替换的原始文本"},
            "new_string": {"type": "string", "description": "替换后的新文本"},
        },
        "required": ["path", "old_string", "new_string"]
    }

    async def execute(self, path: str, old_string: str, new_string: str) -> str:
        p = self._resolve(path)
        content = p.read_text(encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return f"[错误] 未在文件中找到要替换的文本"
        if count > 1:
            return f"[错误] 找到 {count} 处匹配，需要提供更多上下文使其唯一"
        p.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
        return "替换成功"

class ListDirTool(Tool):
    name = "list_dir"
    description = "列出目录内容，返回文件树形结构。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认为 workspace 根目录"},
        }
    }

    async def execute(self, path: str = ".") -> str:
        p = self._resolve(path)
        lines = []
        for item in sorted(p.iterdir()):
            prefix = "📁 " if item.is_dir() else "📄 "
            lines.append(f"{prefix}{item.name}")
        return "\n".join(lines) or "(空目录)"
```

#### tools/shell.py
```python
import asyncio
from .base import Tool

class ExecTool(Tool):
    name = "exec"
    description = "在 shell 中执行命令，返回 stdout + stderr。"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 30", "default": 30},
            "cwd": {"type": "string", "description": "工作目录，默认为 workspace"},
        },
        "required": ["command"]
    }

    def __init__(self, workspace, timeout: int = 30):
        self.workspace = workspace
        self.default_timeout = timeout

    async def execute(self, command: str, timeout: int = None, cwd: str = None) -> str:
        timeout = timeout or self.default_timeout
        cwd = cwd or str(self.workspace)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")
            result = ""
            if output:
                result += f"STDOUT:\n{output}"
            if error:
                result += f"\nSTDERR:\n{error}"
            result += f"\n[退出码: {proc.returncode}]"
            return result.strip()
        except asyncio.TimeoutError:
            return f"[超时] 命令执行超过 {timeout} 秒"
```

#### tools/web.py
```python
import httpx
from .base import Tool

class WebSearchTool(Tool):
    name = "web_search"
    description = "使用 Brave Search 搜索网络，返回摘要和链接列表。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "count": {"type": "integer", "description": "结果数量，默认 5", "default": 5},
        },
        "required": ["query"]
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def execute(self, query: str, count: int = 5) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count},
                headers={"X-Subscription-Token": self.api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        results = data.get("web", {}).get("results", [])
        lines = []
        for r in results:
            lines.append(f"## {r['title']}\n{r['url']}\n{r.get('description', '')}")
        return "\n\n".join(lines) or "未找到结果"

class WebFetchTool(Tool):
    name = "web_fetch"
    description = "抓取网页内容并转为 Markdown 格式文本。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要抓取的网页 URL"},
        },
        "required": ["url"]
    }

    async def execute(self, url: str) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text
        # 使用 markdownify 或 html2text 转换
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            return h.handle(html)[:8000]
        except ImportError:
            # 降级：简单去除 HTML 标签
            import re
            return re.sub(r"<[^>]+>", "", html)[:8000]
```

### 6.4 MCP 客户端（tools/mcp_client.py）

```python
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from .base import Tool
from .registry import ToolRegistry

class MCPToolWrapper(Tool):
    """将单个 MCP 工具包装为标准 Tool 接口。"""

    def __init__(self, server_name: str, tool_def: dict, session: ClientSession):
        self._name = f"mcp_{server_name}_{tool_def['name']}"
        self._description = f"[{server_name}] {tool_def.get('description', '')}"
        self._parameters = tool_def.get("inputSchema", {"type": "object", "properties": {}})
        self._session = session
        self._original_name = tool_def["name"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return self._parameters

    async def execute(self, **kwargs) -> str:
        result = await self._session.call_tool(self._original_name, kwargs)
        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
        return "\n".join(parts) or "(无输出)"


async def connect_mcp_servers(
    servers: list[dict],
    registry: ToolRegistry,
    exit_stack: AsyncExitStack,
) -> None:
    """
    连接所有 MCP 服务器，将其工具注册到 ToolRegistry。
    exit_stack 管理生命周期，在 AgentLoop 关闭时统一清理。
    
    servers 格式：
    [
        {"name": "filesystem", "transport": "stdio",
         "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
        {"name": "my-api", "transport": "sse",
         "url": "http://localhost:8080/sse"},
    ]
    """
    for server in servers:
        name = server["name"]
        transport = server.get("transport", "stdio")
        
        try:
            if transport == "stdio":
                params = StdioServerParameters(
                    command=server["command"][0],
                    args=server["command"][1:],
                    env=server.get("env"),
                )
                read, write = await exit_stack.enter_async_context(
                    stdio_client(params)
                )
            elif transport == "sse":
                read, write = await exit_stack.enter_async_context(
                    sse_client(server["url"])
                )
            else:
                raise ValueError(f"不支持的 MCP transport: {transport}")

            session = await exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            
            # 列出并注册所有工具
            tools_response = await session.list_tools()
            for tool_def in tools_response.tools:
                wrapper = MCPToolWrapper(
                    server_name=name,
                    tool_def={
                        "name": tool_def.name,
                        "description": tool_def.description,
                        "inputSchema": tool_def.inputSchema.model_dump()
                                       if hasattr(tool_def.inputSchema, "model_dump")
                                       else dict(tool_def.inputSchema),
                    },
                    session=session,
                )
                registry.register(wrapper)
                
        except Exception as e:
            print(f"[警告] 连接 MCP 服务器 '{name}' 失败: {e}")
```

---

## 七、上下文记忆系统

### 7.1 ContextBuilder（agent/context.py）

```python
from pathlib import Path
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

    def build_system_prompt(self, session_id: str) -> str:
        """构建 System Prompt（静态部分 + 动态记忆）。"""
        parts = []

        # 1. 角色定义
        parts.append(self._identity())

        # 2. 工作目录引导文件（如果存在）
        for fname in ["AGENTS.md", "SOUL.md", "USER.md"]:
            f = self.workspace / fname
            if f.exists():
                parts.append(f"## {fname}\n{f.read_text()}")

        # 3. 长期记忆
        memory_ctx = self.memory.get_memory_context(session_id)
        if memory_ctx:
            parts.append(f"## 长期记忆\n{memory_ctx}")

        # 4. Always Skills（始终注入的技能）
        always_skills = self.skills.get_always_skills()
        if always_skills:
            parts.append(always_skills)

        # 5. 可用技能摘要（供 Agent 按需读取）
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(skills_summary)

        return "\n\n---\n\n".join(parts)

    def build_messages(
        self,
        history: list[dict],
        user_content: str,
        session_id: str,
    ) -> list[dict]:
        """组合完整消息列表：system + 历史 + 当前消息。"""
        from datetime import datetime
        
        system_prompt = self.build_system_prompt(session_id)
        
        # runtime context（临时信息，不保存到历史）
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
        if self._RUNTIME_TAG in content:
            lines = content.split("\n")
            # 去掉标记行及后续的 runtime 行
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
        return content

    def _identity(self) -> str:
        return (
            "你是一个强大的 AI 助手，能够使用多种工具完成任务。\n"
            f"工作目录：{self.workspace}\n"
            "请尽可能帮助用户，遇到不确定的事情可以先用工具探索。"
        )
```

### 7.2 MemoryManager（agent/memory.py）

```python
import asyncio
from pathlib import Path
from datetime import datetime

class MemoryManager:
    """
    双层记忆架构：
    - memory_md: 结构化长期记忆（用户偏好、重要事实）
    - history_md: 时间线日志（[YYYY-MM-DD HH:MM] 格式，可 grep）
    
    整合时机：当估算的 prompt token 数超过 context_window_tokens 阈值。
    整合方式：调用 LLM 自身将旧对话总结写入记忆。
    """

    def __init__(self, db_manager, context_window_tokens: int = 65536):
        self.db = db_manager
        self.context_window_tokens = context_window_tokens
        self._locks: dict[str, asyncio.Lock] = {}  # 每个 session 独立锁，防并发整合

    def get_memory_context(self, session_id: str) -> str:
        """同步读取记忆（供 ContextBuilder 调用）。"""
        # 注意：实际实现中需要 async，这里说明接口
        ...

    async def get_memory_context_async(self, session_id: str) -> str:
        memory = await self.db.get_memory(session_id)
        if not memory:
            return ""
        parts = []
        if memory["memory_md"]:
            parts.append(f"### 结构化记忆\n{memory['memory_md']}")
        if memory["history_md"]:
            parts.append(f"### 历史摘要\n{memory['history_md'][-2000:]}")  # 最近 2000 字符
        return "\n\n".join(parts)

    async def maybe_consolidate(
        self,
        session_id: str,
        messages: list[dict],
        provider,
        model: str,
    ) -> bool:
        """
        检查是否需要整合记忆，需要则执行。
        返回 True 表示执行了整合。
        """
        estimated_tokens = self._estimate_tokens(messages)
        if estimated_tokens < self.context_window_tokens * 0.8:
            return False

        lock = self._locks.setdefault(session_id, asyncio.Lock())
        if lock.locked():
            return False  # 已有整合在进行中，跳过

        async with lock:
            await self._consolidate(session_id, messages, provider, model)
            return True

    async def _consolidate(self, session_id, messages, provider, model):
        """调用 LLM 整合旧对话到记忆文件。"""
        # 找到需要整合的消息（未整合的旧消息）
        old_messages = await self.db.get_unconsolidated_messages(session_id, limit=50)
        if not old_messages:
            return

        # 获取现有记忆
        memory = await self.db.get_memory(session_id) or {}

        consolidation_prompt = f"""
请将以下对话历史整合到记忆系统中，调用 save_memory 工具保存。

## 现有结构化记忆
{memory.get('memory_md', '（无）')}

## 现有历史日志（最近部分）
{memory.get('history_md', '（无）')[-1000:]}

## 需要整合的对话
{self._format_messages_for_consolidation(old_messages)}

请：
1. 更新结构化记忆（保留重要偏好、事实、偏好设置）
2. 追加历史日志条目（格式：[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 一句话摘要）
"""
        save_memory_tool = {
            "type": "function",
            "function": {
                "name": "save_memory",
                "description": "保存整合后的记忆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_md": {"type": "string", "description": "更新后的结构化记忆"},
                        "history_entry": {"type": "string", "description": "新增的历史日志条目"},
                    },
                    "required": ["memory_md", "history_entry"]
                }
            }
        }

        response = await provider.chat(
            messages=[{"role": "user", "content": consolidation_prompt}],
            tools=[save_memory_tool],
            model=model,
        )

        if response.has_tool_calls:
            for tc in response.tool_calls:
                if tc.name == "save_memory":
                    existing_history = memory.get("history_md", "")
                    new_history = existing_history + "\n" + tc.arguments.get("history_entry", "")
                    await self.db.save_memory(
                        session_id,
                        memory_md=tc.arguments.get("memory_md", ""),
                        history_md=new_history,
                    )
                    # 标记这些消息为已整合
                    await self.db.mark_consolidated(session_id, [m["id"] for m in old_messages])

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """粗略估算 token 数（按字符数 / 4 估算）。"""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 4

    def _format_messages_for_consolidation(self, messages: list[dict]) -> str:
        lines = []
        for m in messages:
            role = m["role"].upper()
            content = m.get("content", "")[:500]  # 截断过长内容
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)
```

---

## 八、Skills 系统

### 8.1 SkillsLoader（agent/skills.py）

```python
import yaml
import re
from pathlib import Path
from dataclasses import dataclass

@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path
    always: bool = False           # 是否始终注入 system prompt
    requires_bins: list[str] = None
    requires_env: list[str] = None

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
        seen = set()
        skills = []
        for d in self.dirs:
            for skill_md in sorted(d.glob("*/SKILL.md")):
                name = skill_md.parent.name
                if name in seen:
                    continue  # 用户自定义优先，跳过同名内置
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
                # 去掉 frontmatter
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
        meta = {}
        match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if match:
            try:
                raw = yaml.safe_load(match.group(1)) or {}
                meta = raw.get("nanobot", raw)  # 兼容 nanobot 格式
            except yaml.YAMLError:
                pass
        return SkillInfo(
            name=name,
            description=meta.get("description", name),
            path=path,
            always=meta.get("always", False),
            requires_bins=meta.get("requires", {}).get("bins", []),
            requires_env=meta.get("requires", {}).get("env", []),
        )

    def _check_requirements(self, skill: SkillInfo) -> bool:
        import shutil, os
        for bin_name in (skill.requires_bins or []):
            if not shutil.which(bin_name):
                return False
        for env_key in (skill.requires_env or []):
            if not os.environ.get(env_key):
                return False
        return True
```

SKILL.md 文件格式：
```markdown
---
description: "使用 ffmpeg 处理音视频文件"
nanobot:
  always: false
  requires:
    bins: ["ffmpeg"]
---

# ffmpeg 工具使用指南

## 视频压缩
使用以下命令压缩视频：
...
```

---

## 九、会话管理

### 9.1 SessionManager（session/manager.py）

```python
import uuid
from datetime import datetime
from pathlib import Path

class SessionManager:
    """
    基于 SQLite 的会话管理器。
    
    会话数据结构：
    - session_id: UUID
    - messages: 有序消息列表（role / content / tool_calls / tool_call_id）
    - last_consolidated: 最后整合到记忆的消息 ID（小于此 ID 的消息不再发给 LLM）
    """

    def __init__(self, db_manager, max_history_messages: int = 200):
        self.db = db_manager
        self.max_history = max_history_messages

    async def create_session(self, title: str = "新会话", model: str = None) -> dict:
        session_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO sessions (id, title, model) VALUES (?, ?, ?)",
            (session_id, title, model)
        )
        return {"id": session_id, "title": title, "model": model}

    async def get_history(self, session_id: str) -> list[dict]:
        """
        返回用于 LLM 调用的历史消息。
        只返回未被整合的消息，并确保从 user turn 开始对齐。
        """
        messages = await self.db.fetch_all(
            """SELECT role, content, tool_calls, tool_call_id, tool_name
               FROM messages
               WHERE session_id = ? AND is_consolidated = 0
               ORDER BY id ASC
               LIMIT ?""",
            (session_id, self.max_history)
        )
        
        # 对齐到第一个 user 消息
        result = []
        found_user = False
        for m in messages:
            if m["role"] == "user":
                found_user = True
            if found_user:
                msg = {"role": m["role"]}
                if m["content"]:
                    msg["content"] = m["content"]
                if m["tool_calls"]:
                    import json
                    msg["tool_calls"] = json.loads(m["tool_calls"])
                if m["tool_call_id"]:
                    msg["tool_call_id"] = m["tool_call_id"]
                    msg["name"] = m["tool_name"]
                result.append(msg)
        return result

    async def save_turn(
        self,
        session_id: str,
        user_content: str,
        new_messages: list[dict],  # 本轮新增的 assistant + tool 消息
    ) -> None:
        """保存本轮对话到数据库。"""
        import json
        
        # 保存用户消息
        await self.db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)",
            (session_id, user_content)
        )
        
        # 保存 assistant 和工具消息
        for msg in new_messages:
            role = msg["role"]
            content = msg.get("content")
            tool_calls = json.dumps(msg["tool_calls"]) if msg.get("tool_calls") else None
            tool_call_id = msg.get("tool_call_id")
            tool_name = msg.get("name")
            await self.db.execute(
                """INSERT INTO messages
                   (session_id, role, content, tool_calls, tool_call_id, tool_name)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, role, content, tool_calls, tool_call_id, tool_name)
            )
        
        # 更新会话的 updated_at
        await self.db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id)
        )
```

---

## 十、Agent 核心循环

### 10.1 AgentLoop（agent/loop.py）

```python
import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path

from ..providers.base import LLMProvider, StreamEvent
from ..tools.registry import ToolRegistry
from ..tools.mcp_client import connect_mcp_servers
from ..session.manager import SessionManager
from .context import ContextBuilder
from .memory import MemoryManager

class AgentLoop:
    """
    核心 ReAct 循环：
    用户输入 → 构建 Prompt → LLM → 工具调用 → LLM → ... → 最终回复
    
    支持：
    - 流式 token 输出（via AsyncGenerator）
    - 工具调用可视化事件
    - 自动记忆整合
    - MCP 工具
    - 最大迭代次数限制
    """

    TOOL_RESULT_MAX_CHARS = 8000  # 工具结果最大长度（防 context 爆炸）

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        session_manager: SessionManager,
        memory_manager: MemoryManager,
        context_builder: ContextBuilder,
        tools: ToolRegistry,
        model: str = "gpt-4o",
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        self.provider = provider
        self.workspace = workspace
        self.sessions = session_manager
        self.memory = memory_manager
        self.context = context_builder
        self.tools = tools
        self.model = model
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def process_stream(self, session_id: str, user_content: str):
        """
        处理用户消息，以异步生成器方式 yield StreamEvent。
        
        事件类型：
        - {"type": "thinking", "content": "..."}         LLM 推理过程
        - {"type": "tool_call", "name": "...", "args": {...}}  工具调用
        - {"type": "tool_result", "name": "...", "content": "..."} 工具结果
        - {"type": "content_delta", "content": "..."}    流式 token（打字机效果）
        - {"type": "done", "content": "..."}             完成
        - {"type": "error", "message": "..."}            出错
        """
        # 1. 获取历史消息
        history = await self.sessions.get_history(session_id)
        
        # 2. 构建消息列表
        messages = self.context.build_messages(history, user_content, session_id)
        
        # 3. 工具定义
        tool_defs = self.tools.get_definitions()
        
        # 4. ReAct 循环
        new_messages = []  # 本轮新增消息（用于保存）
        final_content = None
        
        try:
            for iteration in range(self.max_iterations):
                # 流式调用 LLM
                accumulated_content = ""
                tool_calls_ready = None
                
                async for event in self.provider.chat_stream(
                    messages=messages,
                    tools=tool_defs,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                ):
                    if event.type == "content_delta":
                        accumulated_content += event.content
                        yield event.__dict__

                    elif event.type == "tool_call":
                        yield event.__dict__  # 实时显示工具调用

                    elif event.type == "tool_calls_ready":
                        tool_calls_ready = event.data

                    elif event.type == "done":
                        final_content = event.content or accumulated_content
                        break

                    elif event.type == "error":
                        yield event.__dict__
                        return

                if tool_calls_ready:
                    # 添加 assistant 消息（含工具调用）
                    tc_content = tool_calls_ready["content"]
                    tc_list = tool_calls_ready["tool_calls"]
                    
                    assistant_msg = {"role": "assistant", "content": tc_content, "tool_calls": [
                        {"id": tc["id"], "type": "function",
                         "function": {"name": tc["name"],
                                      "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
                        for tc in tc_list
                    ]}
                    messages.append(assistant_msg)
                    new_messages.append(assistant_msg)
                    
                    # 执行所有工具调用
                    for tc in tc_list:
                        result = await self.tools.execute(tc["name"], tc["arguments"])
                        
                        # 截断超长结果
                        if len(result) > self.TOOL_RESULT_MAX_CHARS:
                            result = result[:self.TOOL_RESULT_MAX_CHARS] + "...[已截断]"
                        
                        yield {"type": "tool_result", "name": tc["name"], "content": result}
                        
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": result,
                        }
                        messages.append(tool_msg)
                        new_messages.append(tool_msg)
                else:
                    # 没有工具调用，循环结束
                    if final_content is not None:
                        assistant_msg = {"role": "assistant", "content": final_content}
                        new_messages.append(assistant_msg)
                    break
            else:
                # 达到最大迭代次数
                final_content = f"已达到最大工具调用次数（{self.max_iterations}），任务可能未完成。"
                yield {"type": "content_delta", "content": final_content}

            yield {"type": "done", "content": final_content}

        finally:
            # 5. 保存本轮对话（无论成功失败）
            if new_messages:
                user_content_clean = self.context.strip_runtime_context(user_content)
                await self.sessions.save_turn(session_id, user_content_clean, new_messages)
            
            # 6. 异步触发记忆整合检查（不阻塞响应）
            asyncio.create_task(
                self.memory.maybe_consolidate(
                    session_id,
                    messages,
                    self.provider,
                    self.model,
                )
            )

    @classmethod
    async def create(cls, config, db_manager) -> "AgentLoop":
        """工厂方法：初始化所有组件并返回 AgentLoop 实例。"""
        from ..providers.litellm_provider import LiteLLMProvider
        from ..tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
        from ..tools.shell import ExecTool
        from ..tools.web import WebSearchTool, WebFetchTool
        from ..tools.mcp_client import connect_mcp_servers
        from ..session.manager import SessionManager
        from .context import ContextBuilder
        from .memory import MemoryManager
        from .skills import SkillsLoader

        workspace = Path(config.workspace)
        workspace.mkdir(parents=True, exist_ok=True)

        provider = LiteLLMProvider(
            api_key=config.llm.api_key,
            api_base=config.llm.api_base,
        )

        session_manager = SessionManager(db_manager)
        memory_manager = MemoryManager(db_manager, config.llm.context_window_tokens)
        skills_loader = SkillsLoader(Path(config.skills_dir))
        context_builder = ContextBuilder(workspace, skills_loader, memory_manager)

        # 注册工具
        tools = ToolRegistry()
        tools.register(ReadFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(WriteFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(EditFileTool(workspace, config.tools.restrict_to_workspace))
        tools.register(ListDirTool(workspace, config.tools.restrict_to_workspace))
        tools.register(ExecTool(workspace, config.tools.shell_timeout))
        if config.tools.brave_api_key:
            tools.register(WebSearchTool(config.tools.brave_api_key))
        tools.register(WebFetchTool())

        # 连接 MCP
        exit_stack = AsyncExitStack()
        if config.mcp_servers:
            await connect_mcp_servers(config.mcp_servers, tools, exit_stack)

        return cls(
            provider=provider,
            workspace=workspace,
            session_manager=session_manager,
            memory_manager=memory_manager,
            context_builder=context_builder,
            tools=tools,
            model=config.llm.default_model,
            max_iterations=config.llm.max_iterations,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
```

---

## 十一、API 层

### 11.1 FastAPI 主入口（main.py）

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import AppConfig
from .database import init_db, get_db_manager
from .agent.loop import AgentLoop
from .api.routes import router as api_router
from .api.websocket import router as ws_router

config = AppConfig()
agent_loop: AgentLoop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    db = get_db_manager()
    app.state.agent = await AgentLoop.create(config, db)
    app.state.config = config
    yield
    # 清理 MCP 连接等资源

app = FastAPI(title="My Agent", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# 生产环境：挂载 Vue 构建产物
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

### 11.2 REST 路由（api/routes.py）

```python
# GET    /api/sessions              # 列出所有会话
# POST   /api/sessions              # 创建新会话
# DELETE /api/sessions/{id}         # 删除会话
# GET    /api/sessions/{id}/messages # 获取历史消息
# PUT    /api/sessions/{id}/title   # 修改会话标题

# GET    /api/models                 # 列出支持的模型
# GET    /api/tools                  # 列出已注册工具
# GET    /api/config                 # 获取当前配置（不含敏感信息）
# PUT    /api/config/model           # 切换模型
```

### 11.3 WebSocket 处理（api/websocket.py）

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

router = APIRouter()

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket 协议：
    
    客户端 → 服务端：
    {"type": "message", "content": "用户消息"}
    {"type": "stop"}                             # 中断当前任务
    
    服务端 → 客户端：
    {"type": "thinking", "content": "..."}       # LLM 推理过程
    {"type": "tool_call", "name": "...", "args": {...}}
    {"type": "tool_result", "name": "...", "content": "..."}
    {"type": "content_delta", "content": "..."}  # 流式 token
    {"type": "done", "content": "..."}           # 完成
    {"type": "error", "message": "..."}          # 错误
    """
    await websocket.accept()
    agent = websocket.app.state.agent
    current_task = None

    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "stop":
                if current_task and not current_task.done():
                    current_task.cancel()
                continue
            
            if data["type"] == "message":
                # 取消前一个任务（如果还在运行）
                if current_task and not current_task.done():
                    current_task.cancel()
                
                async def stream_response():
                    try:
                        async for event in agent.process_stream(
                            session_id=session_id,
                            user_content=data["content"]
                        ):
                            await websocket.send_json(event)
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": str(e)})
                
                import asyncio
                current_task = asyncio.create_task(stream_response())

    except WebSocketDisconnect:
        if current_task:
            current_task.cancel()
```

---

## 十二、前端设计（Vue 3）

### 12.1 整体布局

```
┌─────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌───────────────────────────────────┐    │
│  │          │  │          对话标题                  │⚙️  │
│  │  会话    │  ├───────────────────────────────────┤    │
│  │  列表    │  │                                   │    │
│  │          │  │  消息气泡区域                     │    │
│  │  [新建]  │  │  ┌─────────────────────┐         │    │
│  │          │  │  │ 👤 用户消息          │         │    │
│  │  会话1   │  │  └─────────────────────┘         │    │
│  │  会话2   │  │  ┌─────────────────────────────┐ │    │
│  │  会话3   │  │  │ 🤖 Assistant                 │ │    │
│  │  ...     │  │  │ [工具调用卡片]               │ │    │
│  │          │  │  │ 最终回复（Markdown 渲染）    │ │    │
│  │          │  │  └─────────────────────────────┘ │    │
│  │          │  ├───────────────────────────────────┤    │
│  │          │  │ [输入框]                    [发送] │    │
│  └──────────┘  └───────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 12.2 核心组件设计

#### ChatPanel.vue
```vue
<!-- 主聊天区域 -->
<template>
  <div class="chat-panel">
    <div class="messages" ref="messagesEl">
      <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />
      <!-- 流式输出中的临时消息 -->
      <StreamingMessage v-if="isStreaming" :events="streamEvents" />
    </div>
    <div class="input-area">
      <n-input v-model:value="inputText" type="textarea" 
               @keydown.enter.exact.prevent="sendMessage"
               placeholder="输入消息（Enter 发送，Shift+Enter 换行）" />
      <n-button @click="sendMessage" :loading="isStreaming">发送</n-button>
      <n-button v-if="isStreaming" @click="stopStream">停止</n-button>
    </div>
  </div>
</template>
```

#### MessageBubble.vue
```vue
<!-- 单条消息，支持 Markdown 渲染 + 工具调用展示 -->
<template>
  <div :class="['message', message.role]">
    <!-- 用户消息 -->
    <div v-if="message.role === 'user'" class="user-content">
      {{ message.content }}
    </div>
    
    <!-- AI 消息（含工具调用） -->
    <div v-else-if="message.role === 'assistant'" class="assistant-content">
      <!-- 推理过程（折叠） -->
      <ThinkingBlock v-if="message.reasoning" :content="message.reasoning" />
      <!-- 工具调用卡片 -->
      <ToolCallCard v-for="tc in message.toolCalls" :key="tc.id" 
                    :tool-call="tc" :result="findResult(tc.id)" />
      <!-- 最终文本（Markdown 渲染） -->
      <div class="markdown" v-html="renderMarkdown(message.content)" />
    </div>
  </div>
</template>
```

#### ToolCallCard.vue
```vue
<!-- 工具调用可视化：名称 + 参数（折叠）+ 结果（折叠） -->
<template>
  <div class="tool-card">
    <div class="tool-header" @click="expanded = !expanded">
      <span class="tool-icon">🔧</span>
      <span class="tool-name">{{ toolCall.name }}</span>
      <span class="status" :class="status">{{ statusText }}</span>
    </div>
    <n-collapse-transition :show="expanded">
      <div class="tool-args">
        <pre>{{ JSON.stringify(toolCall.args, null, 2) }}</pre>
      </div>
      <div class="tool-result" v-if="result">
        <pre>{{ result }}</pre>
      </div>
    </n-collapse-transition>
  </div>
</template>
```

### 12.3 WebSocket 客户端（api/websocket.ts）

```typescript
export type StreamEvent = 
  | { type: "thinking"; content: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; content: string }
  | { type: "content_delta"; content: string }
  | { type: "done"; content: string }
  | { type: "error"; message: string }

export class AgentWebSocket {
  private ws: WebSocket | null = null
  private sessionId: string

  constructor(sessionId: string) {
    this.sessionId = sessionId
  }

  connect(onEvent: (event: StreamEvent) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`ws://localhost:8000/ws/${this.sessionId}`)
      this.ws.onopen = () => resolve()
      this.ws.onerror = reject
      this.ws.onmessage = (e) => onEvent(JSON.parse(e.data))
    })
  }

  sendMessage(content: string): void {
    this.ws?.send(JSON.stringify({ type: "message", content }))
  }

  stop(): void {
    this.ws?.send(JSON.stringify({ type: "stop" }))
  }

  disconnect(): void {
    this.ws?.close()
  }
}
```

### 12.4 Pinia Store（stores/chat.ts）

```typescript
export const useChatStore = defineStore("chat", () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const streamEvents = ref<StreamEvent[]>([])  // 当前流式事件缓冲

  async function sendMessage(content: string) {
    if (!currentSessionId.value) return
    
    // 乐观更新：立即显示用户消息
    messages.value.push({ role: "user", content, id: Date.now().toString() })
    
    isStreaming.value = true
    streamEvents.value = []
    
    const ws = new AgentWebSocket(currentSessionId.value)
    await ws.connect((event) => {
      streamEvents.value.push(event)
      
      if (event.type === "done") {
        // 流式结束，将临时消息固化为完整消息
        isStreaming.value = false
        messages.value.push(buildFinalMessage(streamEvents.value))
        streamEvents.value = []
      }
    })
    
    ws.sendMessage(content)
  }

  return { sessions, currentSessionId, messages, isStreaming, streamEvents, sendMessage }
})
```

---

## 十三、Python 依赖（pyproject.toml）

```toml
[project]
name = "my-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # 后端框架
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "websockets>=13.0",
    
    # LLM
    "litellm>=1.50.0",
    
    # 数据库
    "aiosqlite>=0.20.0",
    
    # 配置
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    
    # MCP
    "mcp>=1.0.0",
    
    # 工具依赖
    "httpx>=0.27.0",        # web_fetch
    "html2text>=2024.2.26", # HTML → Markdown
    "jsonschema>=4.23.0",   # 工具参数验证
    
    # Skills
    "pyyaml>=6.0.2",
    
    # 日志
    "loguru>=0.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]
```

---

## 十四、开发顺序建议

按以下顺序开发，每步完成后均可独立验证：

```
阶段 1（核心可用）—— 约 2-3 天
  ✅ Step 1: database.py + config.py
  ✅ Step 2: providers/litellm_provider.py（非流式）
  ✅ Step 3: tools/base.py + tools/registry.py + tools/filesystem.py + tools/shell.py
  ✅ Step 4: session/manager.py
  ✅ Step 5: agent/loop.py（非流式版本）
  ✅ Step 6: main.py + api/routes.py（REST 接口）
  ✅ 验证：curl 调用 POST /api/sessions + POST /api/chat，Agent 能用工具完成任务

阶段 2（流式 + Web UI）—— 约 2-3 天
  ✅ Step 7: providers/litellm_provider.py（流式 chat_stream）
  ✅ Step 8: agent/loop.py（流式版本）
  ✅ Step 9: api/websocket.py
  ✅ Step 10: Vue 3 前端（基础聊天界面）
  ✅ 验证：Web 界面可以流式对话，工具调用有可视化

阶段 3（记忆 + Skills）—— 约 1-2 天
  ✅ Step 11: agent/context.py（ContextBuilder）
  ✅ Step 12: agent/memory.py（MemoryManager）
  ✅ Step 13: agent/skills.py（SkillsLoader）
  ✅ 验证：多轮对话有记忆，Skills 能被 Agent 按需读取

阶段 4（MCP + 完善）—— 约 1-2 天
  ✅ Step 14: tools/mcp_client.py
  ✅ Step 15: tools/web.py（web_search + web_fetch）
  ✅ Step 16: 前端完善（会话列表、工具调用卡片、设置面板）
  ✅ 验证：MCP 服务可以接入，工具调用有完整 UI 展示
```

---

## 十五、关键设计决策说明

| 决策 | 选择 | 理由 |
|------|------|------|
| 流式协议 | WebSocket | 双向通信，可发送 stop 指令；SSE 仅单向 |
| 存储 | SQLite + aiosqlite | 零部署，本地运行；消息结构化查询方便 |
| LLM 接入 | LiteLLM | 一套代码接入 20+ 模型；流式/非流式统一 API |
| 工具结果截断 | 8000 字符 | 防止工具结果占满 context window |
| 记忆整合触发 | Token 数 > 80% 阈值 | 不硬编码轮次，适应不同长度的对话 |
| MCP 生命周期 | AsyncExitStack | 统一管理连接，应用关闭时自动清理 |
| Skills 加载 | 渐进式（摘要注入，按需读取） | 节省 token；大量 Skills 时不爆 context |
| 前端状态 | Pinia | Vue 官方推荐；与 Composition API 完美配合 |
| 并发安全 | 每 session 独立 asyncio.Lock（记忆整合时） | 防止同一会话并发整合产生数据竞争 |
```
