# Private Everything Agent（梦蝶）

基于 Python FastAPI + Vue 3 的本地个人 / 编码 AI Agent。既能像"住在 workspace 里的助手"处理日常写作，也能把任意目录当作项目根做真实编码工作（读文件、改代码、跑命令、看 diff）。

## 核心特性

### Agent 能力
- 🤖 12 家主流 LLM 服务商（OpenAI / Anthropic / Google Gemini / DeepSeek / xAI / Groq / Mistral / OpenRouter / Ollama / 火山引擎 / 阿里 DashScope / 智谱 GLM），首启种子注入 50+ 模型
- ⚡ 全链路流式：token 打字机 + `reasoning_content` 思维链 + 工具调用参数增量显示
- 🧠 双层记忆：单会话 AutoCompact 摘要 + 跨会话极简用户画像
- 📚 Skills 系统：系统内置 + 用户覆盖，依赖不满足自动隐藏
- 🤝 SubAgent 并行派发（`spawn_subagents`），并发上限可调
- 🔌 MCP 协议：stdio / SSE / Streamable-HTTP 三种传输，运行时热插拔
- ⏰ 定时任务：cron 5 字段 + `@every` 间隔语法，全局广播通知

### AI 编码工作流
- 📁 **会话级工作目录**：每个会话可绑定任意本地目录，工具路径解析自动切换
- 🔒 **破坏性工具确认**：`write_file` / `edit_file` / `multi_edit` / `apply_patch` / `exec` 执行前弹卡，可选"信任此目录 / 信任此命令前缀"持久化
- 🛠 **完整编码工具**：`glob` / `grep` / `multi_edit` / `apply_patch` 全套，`grep` 优先走 ripgrep 回退纯 Python
- 🌲 **右侧文件树**：实时反映目录结构，Git 状态徽章（M/A/?/D），@ 补全 / 右键附加到会话
- 📦 **附件系统**："发一次就消费掉"的路径附件，chip 展示，与消息一起持久化
- 💻 **网页内嵌终端**：xterm.js + Unix PTY，多 tab 侧边抽屉，独立于 Agent 的用户操作面
- 📖 **只读代码浏览器**：双击文件树打开，多 tab，语法高亮，可与聊天同屏
- 🧭 **项目自动探测**：识别语言 / 框架 / 包管理器 / 常用脚本，注入 system prompt

### 交互与 UI
- 🎨 Naive UI 组件库，深色元素融合的浅色主题
- 📎 文件上传解析（txt/md/json/csv/yaml/常见代码/docx/xlsx，最大 10MB）
- 🖼 多模态：视觉模型自动启用图片粘贴/拖拽
- 🪟 左右侧栏可折叠 + 鼠标拖拽调宽（含持久化）
- 🎯 工具调用卡片按类型渲染：edit 类显示 diff，read 类高亮代码，exec 显示命令 + cwd
- ❌ 错误分类：Rate Limit / Auth / Context Overflow / Timeout 等 10 类，前端给对应建议

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

API Key 推荐通过 Web UI「设置 → 服务商」面板填入（写入 SQLite，启动时自动注入环境变量）。首次启动会种子注入 12 家 Provider 配置。

如需通过 `.env` 覆盖默认值（可选）：

```bash
cp .env.example .env
```

```env
# LLM 默认值（可被 UI 设置或会话级 override 覆盖）
LLM__DEFAULT_MODEL=deepseek/deepseek-chat
LLM__MAX_TOKENS=8192
LLM__TEMPERATURE=0.1
LLM__CONTEXT_WINDOW_TOKENS=65536
LLM__MAX_ITERATIONS=40                # ReAct 最大工具调用轮数
LLM__API_BASE=                        # 自定义 OpenAI 兼容端点

# 工具
TOOLS__BRAVE_API_KEY=                 # web_search 需要
TOOLS__RESTRICT_TO_WORKSPACE=true     # 仅当会话 working_dir=NULL 时生效
TOOLS__SHELL_TIMEOUT=30               # exec 单次超时秒数
TOOLS__SUBAGENT_CONCURRENCY=5         # SubAgent 并发上限
TOOLS__CONFIRM_REQUIRED_TOOLS=exec,write_file,edit_file,multi_edit,apply_patch

# 路径
WORKSPACE=./workspace
SKILLS_DIR=./skills
```

### 3. 启动

```bash
./start.sh   # 生产（FastAPI 同时托管前端 dist/）→ http://localhost:8000
./dev.sh     # 开发（后端热重载 + Vite dev server）→ http://localhost:5173
```

## 沙箱模式与工作目录

会话的行为由是否设置 `working_dir` 决定：

| 场景 | working_dir | sandbox_mode | 相对路径基准 | 边界 |
|------|-------------|--------------|-----------|------|
| 老会话 / 日常助手 | `NULL` | `workspace` | `./workspace/` | 强制关在 workspace 内 |
| 编码会话 | `/path/to/project` | `free` | 该项目根 | 无沙箱，可越出访问系统文件 |

在会话头部点 🗂 或右键会话列表 → "设置工作目录"，输入绝对路径即可绑定。绑定后：
- 右侧自动出现文件树面板（含 Git 徽章）
- 系统提示注入 cwd 简报 + 项目类型探测（语言/框架/包管理/脚本）+ 项目根的 `AGENTS.md`（若存在）
- 所有相对路径基准切到该项目
- `exec` 默认 cwd 为该项目根

## 破坏性工具确认协议

`exec` / `write_file` / `edit_file` / `multi_edit` / `apply_patch` 执行前，WebSocket 会先推 `tool_confirm` 事件，前端渲染确认卡：

- **Edit 类**：内联展示 unified diff（红绿高亮，行号定位）
- **Exec 类**：显示命令 + cwd + 环境说明
- **按钮**：`允许` / `拒绝` / `信任此目录` / `信任此命令前缀`（后两个持久化到 session_metadata，下次自动放行）

被拒绝的工具会向 LLM 返回 `"[已被用户拒绝]"`，Agent 会自然改用其他手段或询问用户。

在「设置 → 信任列表」可查看和撤销所有已授信项。

## 目录结构

```
private-everything-agent/
├── backend/                # Python 后端
│   ├── main.py             # FastAPI 入口（lifespan + Provider 种子）
│   ├── config.py           # Pydantic Settings
│   ├── database.py         # aiosqlite（8 张表 + 迁移调度）
│   ├── scheduler.py        # APScheduler 定时任务
│   ├── migrations/         # 001_files / 002_session_date / 003_working_dir
│   ├── agent/
│   │   ├── loop.py         # ReAct 主循环（流式 + SubAgent + confirmer）
│   │   ├── context.py      # System prompt 装配（人格→操作规范→SOUL→USER→项目 AGENTS→cwd 简报→摘要→画像→Skills）
│   │   ├── memory.py       # AutoCompact + 用户画像
│   │   ├── confirmer.py    # ConfirmationBroker（pending Future 池）
│   │   ├── project_probe.py# 项目类型探测（缓存到 session_metadata）
│   │   └── skills.py       # Skills 加载与依赖检测
│   ├── providers/
│   │   ├── base.py         # LLMProvider 抽象
│   │   ├── litellm_provider.py  # LiteLLM 实现（流式 + reasoning）
│   │   └── key_manager.py  # Provider Key/模型注册
│   ├── tools/
│   │   ├── base.py         # Tool / StreamingTool
│   │   ├── registry.py     # 注册表 + _ctx 注入 + 全局/会话级禁用
│   │   ├── context.py      # ToolContext dataclass（cwd/sandbox_mode/trusts）
│   │   ├── filesystem.py   # read_file / write_file / edit_file / list_dir / read_skill
│   │   ├── coding.py       # glob / grep / multi_edit / apply_patch
│   │   ├── shell.py        # exec（可传 cwd/timeout 覆盖）
│   │   ├── web.py          # web_search / web_fetch
│   │   ├── subagent.py     # spawn_subagents（Semaphore 限流）
│   │   ├── task_tools.py   # create/list/update/delete_task
│   │   ├── mcp_client.py   # MCP Manager
│   │   └── file_parser.py  # 上传文件解析
│   ├── session/manager.py  # 会话 CRUD + trusts CRUD + working_dir setter
│   ├── utils/
│   │   ├── errors.py       # classify_error（10 类错误分类）
│   │   └── llm_logger.py   # 每日 JSONL LLM 日志
│   └── api/
│       ├── routes.py       # 聚合 routers/
│       ├── routers/        # sessions / providers / models / tools / tasks / templates / mcp / skills
│       ├── websocket.py    # /ws/{session_id}（含 confirm 协议 + 文件解析）
│       ├── terminal.py     # /ws/terminal/{session_id}（PTY）
│       ├── connection_manager.py
│       └── deps.py
├── frontend/               # Vue 3 + Vite + Pinia
│   └── src/
│       ├── App.vue         # 主布局（可折叠三列 + 抽屉）
│       ├── components/
│       │   ├── ChatPanel.vue         # 输入 + @补全 + 附件 chip + confirm 卡渲染
│       │   ├── SessionList.vue       # 会话列表 + cwd 徽章 + 右键菜单
│       │   ├── MessageBubble.vue     # 消息气泡（Markdown / 图片 / 附件路径）
│       │   ├── ToolCallCard.vue      # 工具卡片（智能预览：diff / code / cmd）
│       │   ├── ToolConfirmDialog.vue # 确认卡（内联，非模态）
│       │   ├── SubAgentBlock.vue     # SubAgent 时间线
│       │   ├── ThinkingBlock.vue     # 思维链
│       │   ├── FileTreePanel.vue     # 右侧文件树（Git 徽章 + 右键 + 拖拽调宽）
│       │   ├── CodeViewer.vue        # 只读代码浏览器（多 tab）
│       │   ├── CodeBlock.vue         # hljs 语法高亮
│       │   ├── DiffView.vue          # Unified diff 红绿渲染
│       │   ├── TerminalPanel.vue     # 终端抽屉（多 tab shell）
│       │   ├── TerminalTabInstance.vue # 单 pty + xterm + ws 实例
│       │   ├── MentionPopover.vue    # @ 文件补全
│       │   ├── WorkingDirPicker.vue  # cwd 选择器
│       │   ├── ResizeHandle.vue      # 通用拖拽把手
│       │   ├── SettingsPanel.vue / SchedulerPanel.vue
│       │   └── settings/             # Model/Provider/Tools/MCP/Skills/Templates/Params/Trusts 8 个 Tab
│       ├── stores/
│       │   ├── chat.ts               # per-session 状态 + 流式 + attachments + pendingConfirms
│       │   ├── settings.ts           # 全局设置
│       │   ├── layout.ts             # 侧栏宽度 / 折叠 / 终端宽度
│       │   ├── terminal.ts           # 终端 tab 集合
│       │   └── codeViewer.ts         # 代码浏览器 tab 集合
│       ├── api/
│       │   ├── http.ts               # REST 客户端
│       │   └── websocket.ts          # WS 事件类型定义
│       └── utils/
│           ├── markdown.ts
│           └── toolPreview.ts        # 工具参数 → diff/code 预览适配
├── skills/                 # 系统内置 Skills（启动时增量同步到 workspace/.skills_cache/）
├── workspace/              # 默认沙箱（working_dir=NULL 的会话在这里活动）
├── data/                   # SQLite DB（自动创建）
├── logs/                   # 每日 JSONL LLM 调用日志
├── AGENTS.md / SOUL.md / USER.md   # 全局人格 / 价值观 / 用户背景（可选）
├── start.sh / dev.sh
└── pyproject.toml
```

## 数据库表（8 张 + 3 迁移）

| 表 | 用途 |
|----|------|
| `sessions` | 主表：含 `parent_id`（SubAgent 链）/ `summary`（AutoCompact）/ `session_date` / `working_dir` |
| `messages` | 消息记录：`tool_calls` / `reasoning` / `input_tokens` / `output_tokens` / `files` / `is_consolidated` |
| `prompt_templates` | 提示词模板（分类 + 排序） |
| `global_settings` | 全局键值（默认模型、context 窗口、禁用工具集） |
| `provider_keys` | Provider Key + Base URL + 模型列表（含模型级 context/max_tokens 覆盖） |
| `scheduled_tasks` | 定时任务（cron / `@every`，绑定固定 session） |
| `mcp_servers` | MCP 服务器配置 |
| `global_memory` | 单行 singleton：跨会话用户画像 |

`session_metadata`（存于 `sessions` 表的 JSON 列）扩展键：
- `trusted_paths: list[str]` — 已授信目录
- `trusted_commands: list[str]` — 已授信命令前缀
- `project_probe: dict` — 项目探测缓存
- `agents_md_hash: str` — 项目 AGENTS.md 哈希（去重注入）
- `tool_overrides: dict[str, bool]` — 会话级工具开关

## 工具列表

| 工具 | 类型 | 需确认 | 说明 |
|------|------|:----:|------|
| `read_file` | 标准 | | 读文件（支持 offset/limit 分块） |
| `write_file` | 标准 | ✅ | 写/创建文件，自动创建父目录 |
| `edit_file` | 标准 | ✅ | 单处精确字符串替换（要求 old_string 唯一） |
| `multi_edit` | 标准 | ✅ | 单文件多处替换（顺序应用 + 失败整体回滚） |
| `apply_patch` | 标准 | ✅ | 应用 unified diff（dry-run 校验 + 原子写入） |
| `list_dir` | 标准 | | 树形列目录 |
| `glob` | 标准 | | 按 glob 模式查找文件（respect .gitignore） |
| `grep` | 标准 | | 内容搜索（优先 ripgrep 回退 Python re） |
| `read_skill` | 标准 | | 按需读取 Skill 完整内容 |
| `exec` | 标准 | ✅ | Shell 命令（cwd 默认取会话 working_dir） |
| `web_search` | 标准 | | Brave Search API |
| `web_fetch` | 标准 | | 抓取网页转 Markdown |
| `spawn_subagents` | 流式 | | 并行派发 SubAgent（Semaphore 限流） |
| `create_task` / `list_tasks` / `update_task` / `delete_task` | 标准 | | 定时任务 CRUD |
| `mcp_*_*` | MCP | 部分 | 来自 MCP 服务器的动态工具 |

- 工具两级控制：会话 override > 全局禁用 > 默认启用
- `confirm_required_tools` 可通过 `.env` 或代码调整；命中「信任列表」时跳过弹卡
- Read/Grep 类不进入确认列表（只读）

## SubAgent 并行执行

- 每个 SubAgent 在独立会话中运行（`parent_id` 关联父会话）
- 通过 `asyncio.gather` 并行派发，`asyncio.Semaphore(TOOLS__SUBAGENT_CONCURRENCY)` 限流
- 所有事件流实时透传到主 Agent 的 WebSocket
- 会话列表点父会话可展开查看 SubAgent 子会话
- SubAgent 不加载 Skills / 记忆，专注单一子任务，最多 20 轮工具调用
- SubAgent 工具列表自动排除 `spawn_subagents`（最大深度 1）
- 可为每个 SubAgent 单独指定允许使用的工具白名单
- SubAgent 继承父会话的 `cwd` 和 `trusted_paths`（避免子任务里降级安全）

## 网页内嵌终端

- 位置：右侧抽屉，从主聊天面板右侧滑出
- 后端：`/api/ws/terminal/{session_id}`，`pty.fork()` 派生子进程，`fcntl` 非阻塞 + `loop.add_reader` 桥接 stdout
- 前端：`xterm@5` + `@xterm/addon-fit`，每 tab 一个独立 pty + ws + xterm 实例
- 多 tab：切换用 `v-show`，隐藏 tab 的 shell 保持后台运行
- 抽屉宽度可拖拽，`layout` store 持久化
- 与 Agent 完全隔离——用户看到的终端 Agent 看不到，反之亦然（避免污染上下文）

## 只读代码浏览器

- 双击文件树中的文件 / `右键 → 用浏览器打开` → 弹出多 tab 抽屉
- `<CodeBlock>` 复用 hljs 高亮，按文件扩展名自动检测语言
- 最多同时保留 12 个 tab（超出顶掉最早的非 active）
- 二进制文件自动识别（前 4KB 查 NUL）
- 大文件截断到 512KB，显示"已截断"标签

## @ 补全 / 右键 / 附件

在输入框中输入 `@`：
1. 弹出补全列表（服务端 `files/search`，走 `.gitignore` + 跳过 `node_modules/.venv/dist/...`）
2. `↑↓` 选择，`Enter/Tab` 确认，`Esc` 取消
3. 命中后**路径不会插入到文本**，而是变成消息上方的 chip（附件）
4. 也可右键文件树 → "附加到下条消息（@）"

发送时行为："**发一次就消费掉**"—— chip 一起随消息发出后立即清空，Agent 收到附加信息后自主决定是否读文件。

## 项目自动探测

绑定 `working_dir` 后，`project_probe` 会检测：

| 探测源 | 提取内容 |
|-------|---------|
| `package.json` | JS/TS、包管理（npm/pnpm/yarn）、框架（Vue/React/Next/Nuxt/...）、scripts |
| `pyproject.toml` / `requirements.txt` | Python、框架（fastapi/django/flask）|
| `Cargo.toml` / `go.mod` / `pom.xml` / `Gemfile` | Rust / Go / Java / Ruby |
| `Makefile` | test / build / dev 目标 |
| `git` | 当前分支 + 脏文件数 |

结果缓存到 `session_metadata.project_probe`，注入 system prompt 的"当前工作目录"简报。

## 文件上传与解析

聊天输入支持点击 / 拖拽 / 粘贴文件，由 `file_parser.py` 提取文本拼入 user 消息：

| 类型 | 处理 |
|------|------|
| 文本 / Markdown / JSON / YAML / CSV | `chardet` 自动识别编码 |
| 常见代码（py/ts/js/go/rs/java/c/...） | UTF-8 直读 |
| `.docx` | `python-docx` 提取段落 + 表格 |
| `.xlsx` | `openpyxl` 提取所有 Sheet |

单文件最大 10MB；不支持的扩展名前端拒绝。
解析后内容持久化到 `messages.files` JSON 列，供历史回放。

## Skills

`SKILL.md`（YAML frontmatter + Markdown 正文），分两类：

- **系统 Skills**：`skills/<name>/SKILL.md`，启动时**整树同步**（含 `references/`、`scripts/` 子目录）到 `workspace/.skills_cache/`
- **用户 Skills**：`workspace/skills/<name>/SKILL.md`，同名覆盖系统

```markdown
---
description: "在 system prompt 中显示的技能摘要"
nanobot:
  requires:
    bins: ["ffmpeg"]     # 不可用时该 Skill 隐藏
    env: ["API_KEY"]
---

# 技能名称
...
```

Agent 通过 `read_skill(name=xxx)` 按需读取完整内容。

## 定时任务

支持 5 字段 cron 和 `@every` 间隔（时区 Asia/Shanghai）：

```
0 9 * * 1-5    # 工作日每天 09:00
@every 30s     # 每 30 秒
@every 5m
@every 2h
```

任务复用固定 session（首次执行创建并写回 DB）；执行完成后通过 WebSocket 全局广播 `task_notification`。

## MCP 配置

「设置 → MCP」面板添加，支持三种传输：

- `stdio`：本地子进程（如 `npx -y @modelcontextprotocol/server-xxx`）
- `sse`：远程 SSE 端点（含自定义 headers）
- `streamable-http`：Streamable HTTP（含自定义 headers）

MCP 工具以 `mcp_{server}_{tool}` 命名注册，运行时可启停 / 重连，无需重启进程。

## 错误分类

后端 `utils/errors.py` 把异常归入 10 类，前端根据 category 显示对应图标 + 建议：

| 类别 | 可重试 | 前端提示 |
|-----|:----:|---------|
| `LLM_RATE_LIMIT` | ✅ | 稍后重试 |
| `LLM_CONTEXT_OVERFLOW` | | 建议清理历史或分会话 |
| `LLM_AUTH` | | 检查 API Key |
| `LLM_MODEL_NOT_FOUND` | | 模型 ID 不存在 |
| `LLM_TIMEOUT` | ✅ | — |
| `LLM_UNKNOWN` | | 通用 |
| `TOOL_PERMISSION_DENIED` | | 静默（用户自己触发） |
| `TOOL_PATH_INVALID` | | 沙箱越界 |
| `TOOL_EXEC_FAILED` | | 命令退出非 0 |
| `TOOL_TIMEOUT` | | — |

## Token 用量与日志

- 每条 assistant 消息持久化 `input_tokens` / `output_tokens`，前端在消息底部展示
- 会话最近一次 `input_tokens` 超过 `context_window_tokens × 80%` 时后台自动 AutoCompact
- 所有 LLM 调用按天写入 `logs/llm-YYYY-MM-DD.log`（JSONL：请求 / 聚合响应 / 耗时 / 错误）

## 个性化配置

在项目根目录放置以下文件（**不在 `workspace/` 内**，避免被 Agent 自身写工具误改）：

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | 完整替换全局人格（不存在则用默认"梦蝶"persona） |
| `SOUL.md` | 价值观与核心原则（追加注入） |
| `USER.md` | 用户背景信息（追加注入） |

绑定 `working_dir` 时，若该项目根目录下有 `AGENTS.md` 或 `CLAUDE.md`，会追加到 system prompt（按 hash 去重）。

**System prompt 装配顺序**：

```
全局 AGENTS.md（或默认 persona）
→ 操作规范（跨工具启发式）
→ SOUL.md → USER.md
→ [项目 AGENTS.md / CLAUDE.md]（若 working_dir 且存在）
→ [工作目录简报：cwd + project_probe + Git]
→ 会话摘要
→ 用户画像
→ Skills 摘要
→ 会话固定日期
```

## 支持的模型

「设置 → 服务商」UI 管理；首次启动种子注入下列 12 家 Provider 的默认模型列表，填入 Key 即可使用：

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
| Ollama（本地） | `ollama/*` | 无（`http://localhost:11434`） |
| 字节跳动 火山引擎 | `volcengine/*` | `VOLCENGINE_API_KEY` |
| 阿里云 DashScope | `dashscope/*` | `DASHSCOPE_API_KEY` |
| 智谱 GLM | `zai/*` | `ZAI_API_KEY` |
| 自定义 OpenAI 兼容 | 任意前缀 + 设置 `api_base` | — |

每个模型可单独覆盖 `context_window_tokens` / `max_tokens` / `reasoning_effort`。

## 记忆系统

双层架构：

- **会话级 AutoCompact 摘要**（`sessions.summary`）：单会话上下文超窗口 80% 时，调用 LLM 把早期消息压缩为 500 字内摘要，原消息标记 `is_consolidated=1`，下次构建上下文只用摘要 + 未整合消息 + 最近 5 轮保留
- **全局极简画像**（`global_memory.memory_md`）：跨会话共享，仅记录值得长期保留的偏好 / 技术栈 / 工作习惯，AutoCompact 后异步增量更新

整合过程对用户透明，失败不影响主流程。异步任务用强引用池托管，防止被 GC 提前中止。

## 常见问题

**Q：从旧版本升级，老会话数据会丢失吗？**
不会。`working_dir=NULL` 的老会话继续在 `./workspace/` 沙箱内工作，行为与之前完全一致。

**Q：为什么 `write_file` 每次都弹确认卡，很烦？**
按"信任此目录"后同目录内后续写入不再弹；或在「设置 → 信任列表」永久管理。也可以从 `TOOLS__CONFIRM_REQUIRED_TOOLS` 移除某工具（不建议）。

**Q：终端里的命令 Agent 能看到吗？**
不能。终端是纯粹的用户操作面，独立 pty，与 Agent 的 exec 工具完全隔离。这是有意设计——你可以随手在终端里做实验而不担心污染 Agent 上下文。

**Q：Grep 没有 ripgrep 会很慢吗？**
默认走 ripgrep（`rg`），检测不到时回退纯 Python `re.compile + rglob`，中小项目够用。装 ripgrep 后立即生效无需重启。

## License

MIT
