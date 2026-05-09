# Private Everything Agent（梦蝶）

基于 Python FastAPI + Vue 3 的本地个人 AI Agent 系统。

## 特性

- 🤖 支持 20+ 主流 LLM（OpenAI、Anthropic、DeepSeek、Gemini、阿里 DashScope、智谱 GLM、火山引擎、Ollama 等）
- ⚡ 流式输出（打字机效果 + 工具调用参数实时流式显示 + 思维链展示）
- 🔧 内置工具：文件读写/编辑、目录浏览、Shell 执行、网页搜索/抓取、技能阅读
- 🤝 SubAgent 并行执行（`spawn_subagents` 工具，多子任务隔离会话同步推进）
- 🔌 MCP 协议支持（stdio / SSE / Streamable-HTTP 三种传输）
- 📎 文件上传与解析（txt/md/json/csv/yaml/常见代码/docx/xlsx，最大 10MB）
- 🖼 多模态输入（视觉模型自动启用图片粘贴/拖拽）
- 💾 SQLite 持久化（会话、消息、token 用量、文件元数据）
- 🧠 双层记忆系统（会话级 AutoCompact 摘要 + 跨会话用户画像）
- 📚 Skills 系统（系统内置 + 用户自定义，可声明依赖）
- 📝 提示词模板库（按分类组织、一键填充）
- ⏰ 定时任务调度（CRON / `@every` 间隔语法，完成后全局广播）
- 🌐 美观的 Web UI（Naive UI 组件库，支持消息复制、Markdown 渲染、代码高亮）

## 快速开始

### 1. 环境准备

```bash
# Python 3.11+
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Node.js 20+（前端构建）
cd frontend
npm install
npm run build
cd ..
```

### 2. 配置

API Key 推荐通过 Web UI 的「设置 → 服务商」面板配置（写入 SQLite，启动时自动注入环境变量）。
首次启动会种子注入 12 个内置 Provider 配置，UI 中填入 Key 即可使用。

如需通过 `.env` 设置默认值（可选）：

```bash
cp .env.example .env
```

```env
# LLM 默认值（可被 UI 设置覆盖）
LLM__DEFAULT_MODEL=deepseek/deepseek-chat
LLM__API_KEY=                         # 兜底 Key（自定义端点用）
LLM__API_BASE=                        # 自定义 OpenAI 兼容端点（可选）
LLM__MAX_TOKENS=4096
LLM__TEMPERATURE=0.1
LLM__CONTEXT_WINDOW_TOKENS=65536
LLM__MAX_ITERATIONS=40                # Agent 最大工具调用循环次数

# 工具配置
TOOLS__BRAVE_API_KEY=                 # 启用 web_search 时填入
TOOLS__RESTRICT_TO_WORKSPACE=true     # 文件操作限制在 workspace/
TOOLS__SHELL_TIMEOUT=30               # Shell 超时秒数

# 路径配置（一般无需修改）
WORKSPACE=./workspace
SKILLS_DIR=./skills
```

### 3. 启动

```bash
# 生产模式（一键启动，FastAPI 同时托管前端静态产物）
./start.sh

# 开发模式（后端热重载 + 前端 Vite 开发服务器）
./dev.sh
```

- 生产模式：访问 http://localhost:8000
- 开发模式：访问 http://localhost:5173

## 目录结构

```
private-everything-agent/
├── backend/                # Python 后端
│   ├── main.py             # FastAPI 入口（lifespan 初始化、种子 Provider）
│   ├── config.py           # Pydantic Settings 配置类
│   ├── database.py         # SQLite 数据库（8 张表 + 迁移脚本调度）
│   ├── scheduler.py        # APScheduler 定时任务调度
│   ├── migrations/         # 数据库迁移脚本（按文件名顺序执行）
│   ├── agent/
│   │   ├── loop.py         # ReAct Agent 循环（流式 + SubAgent 转发）
│   │   ├── context.py      # 系统提示构建（人格 + 摘要 + 画像 + Skills）
│   │   ├── memory.py       # 双层记忆（AutoCompact + 用户画像）
│   │   └── skills.py       # Skills 加载与可用性检测
│   ├── providers/
│   │   ├── base.py         # LLMProvider 抽象基类
│   │   ├── litellm_provider.py  # LiteLLM 实现（流式 + 思维链 + usage）
│   │   └── key_manager.py  # Provider Key / 模型参数注册表
│   ├── tools/
│   │   ├── base.py         # Tool / StreamingTool 基类
│   │   ├── registry.py     # 工具注册表（全局禁用 + 会话级 override）
│   │   ├── filesystem.py   # read_file / write_file / edit_file / list_dir / read_skill
│   │   ├── shell.py        # exec（Shell 命令执行）
│   │   ├── web.py          # web_search / web_fetch
│   │   ├── subagent.py     # spawn_subagents（并行 SubAgent，StreamingTool）
│   │   ├── mcp_client.py   # MCP 服务器管理与工具动态注册
│   │   ├── task_tools.py   # create_task / list_tasks / update_task / delete_task
│   │   └── file_parser.py  # 文件上传解析（chardet/python-docx/openpyxl）
│   ├── session/
│   │   └── manager.py      # 会话 CRUD，SubAgent 子会话创建
│   ├── utils/
│   │   └── llm_logger.py   # 每日 JSONL LLM 调用日志（logs/llm-YYYY-MM-DD.log）
│   └── api/
│       ├── routes.py       # 聚合 routers/ 子路由
│       ├── routers/        # sessions/providers/models/tools/tasks/templates/mcp/skills
│       ├── websocket.py    # WebSocket /ws/{session_id}（含文件解析）
│       ├── connection_manager.py  # WebSocket 连接池与广播
│       └── deps.py         # FastAPI 依赖注入
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── components/
│       │   ├── ChatPanel.vue       # 主聊天界面（输入 + 文件/图片上传 + 工具栏）
│       │   ├── SessionList.vue     # 会话列表（含 SubAgent 子会话展开）
│       │   ├── MessageBubble.vue   # 消息气泡（Markdown + 复制 + 文件附件）
│       │   ├── ToolCallCard.vue    # 工具调用卡片（实时参数流式显示）
│       │   ├── SubAgentBlock.vue   # SubAgent 执行时间线
│       │   ├── ThinkingBlock.vue   # 思维链展示
│       │   ├── SchedulerPanel.vue  # 定时任务管理面板
│       │   ├── SettingsPanel.vue   # 设置抽屉容器
│       │   └── settings/           # ModelTab/ProviderTab/ToolsTab/MCPTab/SkillsTab/TemplatesTab/ParamsTab
│       ├── stores/
│       │   ├── chat.ts     # 聊天状态（per-session 状态 Map / 流式 / SubAgent）
│       │   └── settings.ts # 全局设置（模型/Provider/Skills/参数）
│       ├── api/
│       │   ├── http.ts     # HTTP 客户端（强类型）
│       │   └── websocket.ts # WebSocket 客户端（强类型事件）
│       └── utils/
│           └── markdown.ts # Markdown 渲染工具
├── skills/                 # 内置系统 Skills（只读，启动时同步到 workspace/.skills_cache/）
├── workspace/              # Agent 工作目录（文件操作沙箱）
│   └── skills/             # 用户自定义 Skills（优先级高于系统同名 Skill）
├── data/                   # SQLite 数据库（自动创建）
├── logs/                   # LLM 调用日志（按天 JSONL）
├── AGENTS.md / SOUL.md / USER.md  # 人格 / 价值观 / 用户背景（可选）
├── start.sh / dev.sh
└── pyproject.toml
```

## 数据库表（8 张）

| 表 | 用途 |
|----|------|
| `sessions` | 会话主表，含 `parent_id`（SubAgent 关联）/ `summary`（AutoCompact 摘要）/ `session_date`（缓存友好日期） |
| `messages` | 消息记录，含 `tool_calls` / `reasoning` / `input_tokens` / `output_tokens` / `files` / `is_consolidated` |
| `prompt_templates` | 提示词模板（分类、排序） |
| `global_settings` | 全局键值设置（默认模型、上下文窗口、禁用工具集等） |
| `provider_keys` | 服务商 Key + Base URL + 模型列表（含模型级 context/max_tokens 参数） |
| `scheduled_tasks` | 定时任务（cron / `@every`，绑定固定 session） |
| `mcp_servers` | MCP 服务器配置（stdio / sse / streamable-http） |
| `global_memory` | 单行 singleton，跨会话共享的用户画像 |

## SubAgent 并行执行

Agent 可通过 `spawn_subagents` 工具将复杂任务拆解为多个子任务并行执行：

- 每个 SubAgent 在独立会话中运行（`parent_id` 关联父会话）
- 通过 `asyncio.gather` 并行派发，所有事件流实时透传到主 Agent
- 会话列表中点击父会话可展开查看 SubAgent 子会话
- SubAgent 不再加载 Skills/记忆，专注于完成单一子任务，最多 20 轮工具调用
- SubAgent 工具列表自动排除 `spawn_subagents`（最大深度 1，防止无限递归）
- 可为每个 SubAgent 单独指定允许使用的工具白名单

## 文件上传与解析

聊天输入框支持点击上传或拖拽文件，由后端 `file_parser.py` 提取纯文本拼入 user 消息：

| 类型 | 处理方式 |
|------|----------|
| 文本 / Markdown / JSON / YAML / CSV | `chardet` 自动识别编码 |
| 常见代码（py/ts/js/go/rs/java/c/...） | UTF-8 直读 |
| `.docx` | `python-docx` 提取段落 + 表格 |
| `.xlsx` | `openpyxl` 提取所有 Sheet |

单文件最大 10MB；不支持的扩展名前端拒绝并提示。
解析后的内容会同时持久化到 `messages.files` JSON 列，供历史回放。

## Skills

Skills 是 `SKILL.md` 文件（带 YAML frontmatter），分为两类：

- 系统 Skills：`skills/<name>/SKILL.md`，启动时增量同步到 `workspace/.skills_cache/`，Agent 通过 `read_skill(name=xxx)` 读取
- 用户 Skills：`workspace/skills/<name>/SKILL.md`，同名时覆盖系统 Skill

`SKILL.md` frontmatter 格式：

```markdown
---
description: "技能描述（用于 system prompt 中的可用技能列表）"
nanobot:
  requires:
    bins: ["ffmpeg"]     # 需要的系统命令（不可用则该 Skill 自动隐藏）
    env: ["API_KEY"]     # 需要的环境变量
---

# 技能名称

技能内容...
```

Agent 启动时会检测依赖；不可用的系统 Skill 不会出现在 system prompt 的 `<available_skills>` 摘要中。
内置 Skill 集（部分）：`docx`、`pdf`、`pptx`、`xlsx`、`webapp-testing`、`canvas-design`、`algorithmic-art`、`mcp-builder`、`brand-guidelines`、`frontend-design` 等。

## 定时任务

支持 5 字段 CRON 和 `@every` 间隔语法（时区 Asia/Shanghai）：

```
0 9 * * 1-5    # 工作日每天 09:00
@every 30s     # 每 30 秒
@every 5m      # 每 5 分钟
@every 2h      # 每 2 小时
```

任务复用固定 session（首次执行创建并写回 DB）；执行完成后通过 WebSocket 全局广播 `task_notification`，前端弹出 toast。

## MCP 配置

在「设置 → MCP」面板中添加，支持三种传输：

- `stdio`：本地子进程（如 `npx -y xxx@latest`）
- `sse`：远程 SSE 端点（含自定义 headers）
- `streamable-http`：Streamable HTTP（含自定义 headers）

MCP 工具以 `mcp_{服务器名}_{工具名}` 命名注册到工具系统，支持运行时启停 / 重连，无需重启进程。

## 提示词模板

「设置 → 模板」可创建分类化的提示词模板，输入框 `/` 触发快速选择并填充。

## Token 用量与日志

- 每条 assistant 消息持久化 `input_tokens` / `output_tokens`，前端在消息底部展示
- 当某会话最近一次 `input_tokens` 超过 `context_window_tokens × 80%` 时，后台自动触发 AutoCompact
- 所有 LLM 调用按天写入 `logs/llm-YYYY-MM-DD.log`（JSONL 原生格式：请求、聚合响应、耗时、错误）

## 支持的模型

通过「设置 → 服务商」UI 管理；首次启动种子注入下列内置 Provider，填入 Key 即可使用：

| 提供商 | Provider Key | 环境变量 |
|--------|-------------|----------|
| OpenAI | `openai/*` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/*` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini/*` | `GEMINI_API_KEY` |
| DeepSeek | `deepseek/*` | `DEEPSEEK_API_KEY` |
| xAI (Grok) | `xai/*` | `XAI_API_KEY` |
| Groq | `groq/*` | `GROQ_API_KEY` |
| Mistral | `mistral/*` | `MISTRAL_API_KEY` |
| OpenRouter | `openrouter/*` | `OPENROUTER_API_KEY` |
| Ollama（本地） | `ollama/*` | 无（默认 `http://localhost:11434`） |
| 字节跳动 火山引擎 | `volcengine/*` | `VOLCENGINE_API_KEY` |
| 阿里云 DashScope | `dashscope/*` | `DASHSCOPE_API_KEY` |
| 智谱 GLM | `zai/*` | `ZAI_API_KEY` |
| 自定义 OpenAI 兼容端点 | 任意前缀 + 设置 `api_base` | — |

每个模型还可单独配置 `context_window_tokens` / `max_tokens` 覆盖全局默认值。

## 工具列表

| 工具 | 类型 | 说明 |
|------|------|------|
| `read_file` | 标准 | 读取文件内容（支持 offset/limit） |
| `write_file` | 标准 | 写入/创建文件，自动创建父目录 |
| `edit_file` | 标准 | 精准字符串替换编辑（要求 old_string 唯一） |
| `list_dir` | 标准 | 树形列出目录（depth 控制层数） |
| `read_skill` | 标准 | 按需读取 Skill 完整内容 |
| `exec` | 标准 | 执行 Shell 命令（可配置超时） |
| `web_search` | 标准 | Brave Search API（需 `TOOLS__BRAVE_API_KEY`） |
| `web_fetch` | 标准 | 抓取网页转 Markdown |
| `spawn_subagents` | 流式 | 并行启动多个 SubAgent 子任务 |
| `create_task` / `list_tasks` / `update_task` / `delete_task` | 标准 | 定时任务管理 |
| `mcp_*_*` | MCP | 来自 MCP 服务器的动态工具 |

`TOOLS__RESTRICT_TO_WORKSPACE=true` 时，所有文件类工具的路径限制在 `workspace/` 沙箱内。
工具支持「全局禁用 + 会话级覆盖」两级控制，优先级：会话 override > 全局禁用 > 默认启用。

## 记忆系统

双层架构：

- **会话级 AutoCompact 摘要（`sessions.summary`）**：单个会话上下文超过窗口 80% 时，调用 LLM 把早期消息压缩为不超过 500 字摘要，标记原消息 `is_consolidated=1`，下次构建上下文时只用摘要 + 未整合消息
- **全局极简画像（`global_memory.memory_md`）**：跨会话共享，仅记录值得长期保留的用户偏好、技术栈、工作习惯，AutoCompact 后台异步增量更新

整合过程对用户透明，失败不影响主流程。

## 个性化配置

在项目根目录放置以下文件自定义 Agent 行为（位置与 `workspace` 隔离，避免被 Agent 自身写工具误改）：

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | 完整替换 Agent 人格设定（不存在时使用默认「梦蝶」persona） |
| `SOUL.md` | 价值观与核心原则（追加注入） |
| `USER.md` | 用户背景信息（追加注入，让 Agent 更了解你） |

System prompt 装配顺序：人格 → 操作规范 → SOUL.md → USER.md → 会话摘要 → 用户画像 → Skills 摘要 → 会话级固定日期。
