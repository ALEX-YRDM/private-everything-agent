# Private Everything Agent（梦蝶）

基于 Python FastAPI + Vue 3 的本地个人 AI Agent 系统。

## 特性

- 🤖 支持 20+ 主流 LLM（OpenAI、Anthropic、DeepSeek、Gemini、Ollama 等）
- ⚡ 流式输出（打字机效果 + 工具调用参数实时流式显示）
- 🔧 内置工具：文件读写/编辑、Shell 执行、网页搜索/抓取
- 🤝 SubAgent 并行执行（spawn_subagents 工具，多子任务同步推进）
- 🔌 MCP 协议支持（可接入任意 MCP 服务器）
- 💾 SQLite 持久化会话与消息
- 🧠 双层记忆系统（结构化记忆 + 时间线日志）
- 📚 Skills 系统（可扩展专项技能）
- ⏰ 定时任务调度（CRON / @every 语法）
- 🌐 美观的 Web UI（Naive UI 组件库）

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

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

最小配置示例：
```env
LLM__DEFAULT_MODEL=deepseek/deepseek-chat
LLM__API_KEY=sk-your-key
```

完整配置项：
```env
# LLM 配置
LLM__DEFAULT_MODEL=deepseek/deepseek-chat
LLM__API_KEY=sk-your-key
LLM__API_BASE=                        # 自定义 OpenAI 兼容端点（可选）
LLM__MAX_TOKENS=8192
LLM__TEMPERATURE=0.7
LLM__CONTEXT_WINDOW_TOKENS=128000
LLM__MAX_ITERATIONS=40               # Agent 最大循环次数

# 工具配置
TOOLS__BRAVE_API_KEY=                 # 网页搜索（可选）
TOOLS__RESTRICT_TO_WORKSPACE=true    # 文件操作限制在 workspace/
TOOLS__SHELL_TIMEOUT=30              # Shell 超时秒数

# 路径配置
WORKSPACE=./workspace
SKILLS_DIR=./skills
```

### 3. 启动

```bash
# 生产模式（一键启动，后端服务前端静态文件）
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
│   ├── main.py             # FastAPI 入口，应用初始化
│   ├── config.py           # Pydantic Settings 配置类
│   ├── database.py         # SQLite 数据库（13 张表）
│   ├── scheduler.py        # APScheduler 定时任务调度
│   ├── agent/
│   │   ├── loop.py         # ReAct Agent 循环（流式 + SubAgent 转发）
│   │   ├── context.py      # 系统提示构建（记忆 + Skills 注入）
│   │   ├── memory.py       # 双层记忆管理（自动触发整合）
│   │   └── skills.py       # Skills 加载与可用性检测
│   ├── providers/
│   │   ├── base.py         # LLMProvider 抽象基类
│   │   ├── litellm_provider.py  # LiteLLM 实现（20+ 提供商）
│   │   └── key_manager.py  # API Key 注册与环境变量注入
│   ├── tools/
│   │   ├── base.py         # Tool / StreamingTool 基类
│   │   ├── registry.py     # 工具注册表（全局 + 会话级控制）
│   │   ├── filesystem.py   # read_file / write_file / edit_file
│   │   ├── shell.py        # exec（Shell 命令执行）
│   │   ├── web.py          # web_search / web_fetch
│   │   ├── subagent.py     # spawn_subagents（并行 SubAgent）
│   │   ├── mcp_client.py   # MCP 服务器管理与工具注册
│   │   └── task_tools.py   # create_task / update_task / delete_task
│   ├── session/
│   │   └── manager.py      # 会话 CRUD，SubAgent 会话创建
│   └── api/
│       ├── routes.py       # REST API（提供商/模型/任务/工具/MCP 等）
│       ├── websocket.py    # WebSocket 端点（流式事件推送）
│       └── connection_manager.py  # WebSocket 连接池与广播
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── components/
│       │   ├── ChatPanel.vue       # 主聊天界面（自动滚动 + 工具覆盖）
│       │   ├── SessionList.vue     # 会话列表（含 SubAgent 子会话）
│       │   ├── MessageBubble.vue   # 消息气泡（Markdown + 工具调用）
│       │   ├── ToolCallCard.vue    # 工具调用卡片（实时参数流式显示）
│       │   ├── SubAgentBlock.vue   # SubAgent 执行时间线
│       │   ├── ThinkingBlock.vue   # Claude 思考过程展示
│       │   ├── SettingsPanel.vue   # 设置面板（模型/工具/MCP/Skills）
│       │   └── SchedulerPanel.vue  # 定时任务管理面板
│       ├── stores/
│       │   ├── chat.ts     # 聊天状态（会话/消息/SubAgent/流式）
│       │   └── settings.ts # 全局设置（模型/工具/提供商）
│       ├── api/
│       │   ├── http.ts     # HTTP 客户端（REST API 封装）
│       │   └── websocket.ts # WebSocket 客户端（强类型事件）
│       └── utils/
│           └── markdown.ts # Markdown 渲染工具
├── skills/                 # 内置 Skills（只读）
├── workspace/              # Agent 工作目录（文件操作沙箱）
│   └── skills/             # 用户自定义 Skills
└── data/                   # SQLite 数据库（自动创建）
```

## SubAgent 并行执行

Agent 可通过 `spawn_subagents` 工具将复杂任务拆解为多个子任务并行执行：

- 每个 SubAgent 运行在独立会话中，互相隔离
- 主会话实时接收子任务进度（流式事件转发）
- 会话列表中子任务会话显示在父会话下方
- 点击子会话可查看详细执行过程（工具调用、思考过程等）
- 最大递归深度为 2，防止无限嵌套
- 可为每个 SubAgent 单独指定允许使用的工具集

工具调用实时可视化：
- 模型生成工具调用参数时实时流式显示（带闪烁光标）
- 参数生成完成后自动切换为格式化 JSON 展示
- SubAgent 的工具调用同样支持实时参数预览

## Skills

Skills 是可注入系统提示的专项技能文档，分为内置（`skills/`）和用户自定义（`workspace/skills/`）两类。

目录结构：
```
skills/
└── my-skill/
    └── SKILL.md
```

`SKILL.md` 格式：
```markdown
---
description: "技能描述（用于 Skills 摘要注入）"
nanobot:
  always: false          # true: 无论何时都注入全文；false: 按需 read_skill
  requires:
    bins: ["ffmpeg"]     # 需要的系统命令
    envs: ["API_KEY"]    # 需要的环境变量
---

# 技能名称

技能内容...
```

Agent 会自动检测技能依赖是否满足，并将可用技能摘要注入系统提示。

## 定时任务

支持 CRON 语法和间隔语法：

```
# CRON（分 时 日 月 周）
0 9 * * 1-5    # 工作日每天 9:00 执行

# 间隔语法
@every 30s     # 每 30 秒
@every 5m      # 每 5 分钟
@every 2h      # 每 2 小时
```

任务执行时会创建独立会话，结果通过 WebSocket 广播给所有在线客户端。

## MCP 配置

在设置面板中添加 MCP 服务器配置（支持 stdio 和 SSE 传输）：
- MCP 工具以 `mcp_{服务器名}_{工具名}` 命名注册到工具系统
- 支持运行时热插拔（无需重启）

## 支持的模型

| 提供商 | 模型示例 | 需要的环境变量 |
|--------|---------|--------------|
| OpenAI | gpt-4o, gpt-4o-mini | OPENAI_API_KEY |
| Anthropic | claude-3-5-sonnet-* | ANTHROPIC_API_KEY |
| DeepSeek | deepseek/deepseek-chat | DEEPSEEK_API_KEY |
| Google | gemini/gemini-2.0-flash | GEMINI_API_KEY |
| 阿里云 DashScope | dashscope/qwen-max | DASHSCOPE_API_KEY |
| 月之暗面 | moonshot/moonshot-v1-128k | MOONSHOT_API_KEY |
| Groq | groq/llama-3.1-70b | GROQ_API_KEY |
| Mistral | mistral/mistral-large | MISTRAL_API_KEY |
| Together AI | together_ai/* | TOGETHERAI_API_KEY |
| OpenRouter | openrouter/* | OPENROUTER_API_KEY |
| Ollama | ollama/* | 无（需本地运行 Ollama） |
| 自定义端点 | 任意 OpenAI 兼容 | LLM__API_BASE |

## 工具列表

| 工具 | 类型 | 说明 |
|------|------|------|
| `read_file` | 标准 | 读取文件内容，支持 offset/limit |
| `write_file` | 标准 | 写入/创建文件，自动创建父目录 |
| `edit_file` | 标准 | 精准字符串替换编辑 |
| `exec` | 标准 | 执行 Shell 命令（可配置超时） |
| `web_search` | 标准 | Brave Search API 网页搜索 |
| `web_fetch` | 标准 | 抓取网页并转换为 Markdown |
| `spawn_subagents` | 流式 | 并行启动多个 SubAgent 子任务 |
| `create_task` | 标准 | 创建定时任务 |
| `update_task` | 标准 | 修改定时任务 |
| `delete_task` | 标准 | 删除定时任务 |
| `mcp_*_*` | MCP | 来自 MCP 服务器的动态工具 |

所有文件类工具在 `TOOLS__RESTRICT_TO_WORKSPACE=true` 时限制在 `workspace/` 目录内。工具支持全局禁用和会话级覆盖，SubAgent 支持工具白名单限制。

## 记忆系统

双层记忆，跨会话共享：

- **结构化记忆（memory_md）**：用户偏好、重要事实、行为规律
- **时间线日志（history_md）**：`[YYYY-MM-DD HH:MM]` 格式的事件记录

当上下文使用量超过 80% 时，自动调用 LLM 进行记忆整合压缩。

## 个性化配置

在 `workspace/` 下放置以下文件自定义 Agent 行为：

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | 完整替换 Agent 人格设定 |
| `SOUL.md` | 价值观与核心原则 |
| `USER.md` | 用户背景信息（让 Agent 更了解你） |
