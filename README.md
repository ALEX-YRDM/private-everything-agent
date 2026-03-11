# Private EveryThing Agent

基于 Python FastAPI + Vue 3 的本地个人 Agent 系统。

## 特性

- 🤖 支持 20+ 主流 LLM（OpenAI、Anthropic、DeepSeek、Gemini、Ollama 等）
- ⚡ 流式输出（打字机效果）
- 🔧 内置工具：文件读写、Shell 执行、网页搜索/抓取
- 🔌 MCP 协议支持（可接入任意 MCP 服务器）
- 💾 SQLite 持久化会话与消息
- 🧠 双层记忆系统（结构化记忆 + 时间线日志）
- 📚 Skills 系统（可扩展专项技能）
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

### 3. 启动

```bash
# 一键启动（后端 + 前端开发服务器）
./start.sh

# 或者分别启动
# 后端
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# 前端（开发模式）
cd frontend && npm run dev
```

访问 http://localhost:5173 使用 Web UI。

## 目录结构

```
my-agent/
├── backend/           # Python 后端
│   ├── main.py        # FastAPI 入口
│   ├── config.py      # 配置（Pydantic Settings）
│   ├── database.py    # SQLite 数据库
│   ├── agent/         # Agent 核心（循环、记忆、Skills）
│   ├── providers/     # LLM 提供商（LiteLLM）
│   ├── tools/         # 工具系统（文件、Shell、Web、MCP）
│   ├── session/       # 会话管理
│   └── api/           # REST + WebSocket API
├── frontend/          # Vue 3 前端
│   └── src/
│       ├── components/ # UI 组件
│       ├── stores/    # Pinia 状态管理
│       ├── api/       # HTTP + WebSocket 客户端
│       └── utils/     # Markdown 渲染等
├── skills/            # 用户自定义 Skills
├── workspace/         # Agent 工作目录
└── data/              # SQLite 数据库（自动创建）
```

## Skills

在 `skills/` 目录下创建子目录，每个目录包含 `SKILL.md`：

```
skills/
└── my-skill/
    └── SKILL.md
```

`SKILL.md` 格式：
```markdown
---
description: "技能描述"
nanobot:
  always: false
  requires:
    bins: ["ffmpeg"]
---

# 技能名称

技能内容...
```

## MCP 配置

在 `.env` 中添加 MCP 服务器配置（通过代码配置，详见 `backend/config.py`）。

## 支持的模型

| 模型 | 需要的环境变量 |
|------|--------------|
| gpt-4o / gpt-4o-mini | OPENAI_API_KEY |
| claude-3-5-sonnet-* | ANTHROPIC_API_KEY |
| deepseek/deepseek-chat | DEEPSEEK_API_KEY |
| gemini/gemini-2.0-flash | GEMINI_API_KEY |
| dashscope/qwen-max | DASHSCOPE_API_KEY |
| moonshot/moonshot-v1-128k | MOONSHOT_API_KEY |
| ollama/* | 无（需本地运行 Ollama） |
