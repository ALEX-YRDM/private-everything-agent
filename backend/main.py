from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from loguru import logger

from .config import AppConfig
from .database import init_db, close_db, get_db_manager
from .agent.loop import AgentLoop
from .scheduler import AgentScheduler
from .api.routes import router as api_router
from .api.websocket import router as ws_router

_DEFAULT_PROVIDERS = [
    {
        "provider": "openai",
        "display_name": "OpenAI",
        "api_base": None,
        "models": [
            {"id": "openai/o4-mini",       "label": "o4-mini"},
            {"id": "openai/o3",            "label": "o3"},
            {"id": "openai/o3-mini",       "label": "o3-mini"},
            {"id": "openai/o1",            "label": "o1"},
            {"id": "openai/o1-mini",       "label": "o1-mini"},
            {"id": "openai/gpt-4.1",       "label": "GPT-4.1"},
            {"id": "openai/gpt-4.1-mini",  "label": "GPT-4.1 mini"},
            {"id": "openai/gpt-4o",        "label": "GPT-4o"},
            {"id": "openai/gpt-4o-mini",   "label": "GPT-4o mini"},
            {"id": "openai/gpt-4-turbo",   "label": "GPT-4 Turbo"},
            {"id": "openai/gpt-3.5-turbo", "label": "GPT-3.5 Turbo"},
        ],
    },
    {
        "provider": "anthropic",
        "display_name": "Anthropic",
        "api_base": None,
        "models": [
            {"id": "anthropic/claude-opus-4-20250514",    "label": "Claude Opus 4"},
            {"id": "anthropic/claude-sonnet-4-20250514",  "label": "Claude Sonnet 4"},
            {"id": "anthropic/claude-3-7-sonnet-20250219","label": "Claude 3.7 Sonnet"},
            {"id": "anthropic/claude-3-5-sonnet-20241022","label": "Claude 3.5 Sonnet"},
            {"id": "anthropic/claude-3-5-haiku-20241022", "label": "Claude 3.5 Haiku"},
        ],
    },
    {
        "provider": "gemini",
        "display_name": "Google Gemini",
        "api_base": None,
        "models": [
            {"id": "gemini/gemini-2.5-pro-preview-05-06","label": "Gemini 2.5 Pro"},
            {"id": "gemini/gemini-2.0-flash",            "label": "Gemini 2.0 Flash"},
            {"id": "gemini/gemini-2.0-flash-lite",       "label": "Gemini 2.0 Flash Lite"},
            {"id": "gemini/gemini-1.5-pro",              "label": "Gemini 1.5 Pro"},
            {"id": "gemini/gemini-1.5-flash",            "label": "Gemini 1.5 Flash"},
        ],
    },
    {
        "provider": "deepseek",
        "display_name": "DeepSeek",
        "api_base": None,
        "models": [
            {"id": "deepseek/deepseek-chat",     "label": "DeepSeek Chat (V3)"},
            {"id": "deepseek/deepseek-reasoner", "label": "DeepSeek Reasoner (R1)"},
        ],
    },
    {
        "provider": "xai",
        "display_name": "xAI (Grok)",
        "api_base": None,
        "models": [
            {"id": "xai/grok-3",      "label": "Grok 3"},
            {"id": "xai/grok-3-mini", "label": "Grok 3 Mini"},
            {"id": "xai/grok-2-1212", "label": "Grok 2"},
        ],
    },
    {
        "provider": "groq",
        "display_name": "Groq",
        "api_base": None,
        "models": [
            {"id": "groq/llama-3.3-70b-versatile",  "label": "Llama 3.3 70B"},
            {"id": "groq/llama-3.1-8b-instant",     "label": "Llama 3.1 8B (fast)"},
            {"id": "groq/mixtral-8x7b-32768",       "label": "Mixtral 8x7B"},
            {"id": "groq/gemma2-9b-it",             "label": "Gemma2 9B"},
            {"id": "groq/qwen-qwq-32b",             "label": "Qwen QwQ 32B"},
        ],
    },
    {
        "provider": "mistral",
        "display_name": "Mistral AI",
        "api_base": None,
        "models": [
            {"id": "mistral/mistral-large-latest", "label": "Mistral Large"},
            {"id": "mistral/mistral-small-latest", "label": "Mistral Small"},
            {"id": "mistral/codestral-latest",     "label": "Codestral"},
            {"id": "mistral/mistral-nemo",         "label": "Mistral Nemo"},
        ],
    },
    {
        "provider": "together_ai",
        "display_name": "Together AI",
        "api_base": None,
        "models": [
            {"id": "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",     "label": "Llama 3.3 70B Turbo"},
            {"id": "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "label": "Llama 3.1 8B Turbo"},
            {"id": "together_ai/Qwen/Qwen2.5-72B-Instruct-Turbo",             "label": "Qwen 2.5 72B Turbo"},
            {"id": "together_ai/deepseek-ai/DeepSeek-R1",                     "label": "DeepSeek R1"},
        ],
    },
    {
        "provider": "openrouter",
        "display_name": "OpenRouter",
        "api_base": None,
        "models": [
            {"id": "openrouter/google/gemini-2.0-flash-001",       "label": "Gemini 2.0 Flash"},
            {"id": "openrouter/anthropic/claude-3.5-sonnet",       "label": "Claude 3.5 Sonnet"},
            {"id": "openrouter/meta-llama/llama-3.3-70b-instruct", "label": "Llama 3.3 70B"},
            {"id": "openrouter/deepseek/deepseek-r1",              "label": "DeepSeek R1"},
            {"id": "openrouter/qwen/qwq-32b",                      "label": "QwQ 32B"},
        ],
    },
    {
        "provider": "perplexity",
        "display_name": "Perplexity",
        "api_base": None,
        "models": [
            {"id": "perplexity/sonar-pro", "label": "Sonar Pro"},
            {"id": "perplexity/sonar",     "label": "Sonar"},
        ],
    },
    {
        "provider": "ollama",
        "display_name": "Ollama (本地)",
        "api_base": "http://localhost:11434",
        "models": [
            {"id": "ollama/llama3.3",        "label": "Llama 3.3"},
            {"id": "ollama/qwen2.5:72b",     "label": "Qwen 2.5 72B"},
            {"id": "ollama/deepseek-r1:14b", "label": "DeepSeek R1 14B"},
            {"id": "ollama/mistral",         "label": "Mistral"},
        ],
    },
    {
        "provider": "volcengine",
        "display_name": "字节跳动 (火山引擎)",
        "api_base": None,
        "models": [
            {"id": "volcengine/doubao-pro-32k",  "label": "Doubao Pro 32K"},
            {"id": "volcengine/doubao-lite-32k", "label": "Doubao Lite 32K"},
        ],
    },
    {
        "provider": "moonshot",
        "display_name": "月之暗面 (Kimi)",
        "api_base": None,
        "models": [
            {"id": "moonshot/moonshot-v1-128k", "label": "Moonshot v1 128K"},
            {"id": "moonshot/moonshot-v1-32k",  "label": "Moonshot v1 32K"},
        ],
    },
    {
        "provider": "dashscope",
        "display_name": "阿里云 (百炼/通义)",
        "api_base": None,
        "models": [
            {"id": "dashscope/qwen-max",            "label": "Qwen Max"},
            {"id": "dashscope/qwen-max-longcontext", "label": "Qwen Max Long"},
            {"id": "dashscope/qwen-plus",           "label": "Qwen Plus"},
            {"id": "dashscope/qwen-turbo",          "label": "Qwen Turbo"},
            {"id": "dashscope/qwen2.5-72b-instruct","label": "Qwen 2.5 72B"},
            {"id": "dashscope/qwen2.5-32b-instruct","label": "Qwen 2.5 32B"},
            {"id": "dashscope/qwq-32b",             "label": "QwQ 32B"},
        ],
    },
    {
        "provider": "minimax",
        "display_name": "MiniMax",
        "api_base": None,
        "models": [
            {"id": "minimax/MiniMax-Text-01", "label": "MiniMax Text-01"},
            {"id": "minimax/abab6.5s-chat",   "label": "ABAB 6.5S"},
            {"id": "minimax/abab6.5g-chat",   "label": "ABAB 6.5G"},
            {"id": "minimax/abab5.5s-chat",   "label": "ABAB 5.5S"},
        ],
    },
    {
        "provider": "zai",
        "display_name": "智谱 AI (GLM)",
        "api_base": None,
        "models": [
            {"id": "zai/glm-4.7",    "label": "glm-4.7"},
            {"id": "zai/glm-4.6",     "label": "glm-4.6"},
            {"id": "zai/glm-4.5",    "label": "glm-4.5"}
        ],
    },
]


async def _seed_default_providers(db) -> None:
    """首次启动时写入内置 Provider + 模型列表（跳过已存在的 provider）。"""
    existing = {row["provider"] for row in await db.list_provider_keys()}
    seeded = 0
    for p in _DEFAULT_PROVIDERS:
        if p["provider"] not in existing:
            await db.upsert_provider_key(
                provider=p["provider"],
                display_name=p["display_name"],
                api_key=None,
                api_base=p.get("api_base"),
                models=p["models"],
            )
            seeded += 1
    if seeded:
        logger.info(f"已种子注入 {seeded} 个默认 Provider 配置")


_BUILTIN_TEMPLATES = [
    {"name": "代码审查", "category": "编程",
     "content": "请对以下代码进行审查，分析：\n1. 代码逻辑正确性\n2. 潜在 bug\n3. 性能问题\n4. 可读性与可维护性\n5. 最佳实践\n\n```\n[粘贴代码]\n```"},
    {"name": "解释代码", "category": "编程",
     "content": "请详细解释以下代码的功能和实现原理：\n\n```\n[粘贴代码]\n```"},
    {"name": "编写单元测试", "category": "编程",
     "content": "请为以下代码编写完整的单元测试，覆盖正常路径和边界情况：\n\n```\n[粘贴代码]\n```"},
    {"name": "调试错误", "category": "编程",
     "content": "我遇到了以下错误，请帮我分析原因并提供解决方案：\n\n错误信息：\n```\n[粘贴错误]\n```\n\n相关代码：\n```\n[粘贴代码]\n```"},
    {"name": "重构建议", "category": "编程",
     "content": "请对以下代码提出重构建议，使其更简洁、可维护：\n\n```\n[粘贴代码]\n```"},
    {"name": "网络调研", "category": "研究",
     "content": "请帮我调研以下主题，搜索最新信息并整理成报告：\n\n主题：[输入主题]\n\n要求：\n1. 搜索权威信息来源\n2. 分析最新进展\n3. 总结关键发现\n4. 附上参考链接"},
    {"name": "竞品分析", "category": "研究",
     "content": "请搜索并对比以下产品/技术的优缺点：\n\n对比对象：[产品A] vs [产品B]\n\n分析维度：功能、性能、价格、社区、适用场景"},
    {"name": "文章摘要", "category": "写作",
     "content": "请对以下内容生成简洁的摘要（不超过 300 字），保留核心要点：\n\n[粘贴内容]"},
    {"name": "润色文章", "category": "写作",
     "content": "请对以下文章进行润色，使其更流畅专业，保持原意不变：\n\n[粘贴文章]"},
    {"name": "中译英", "category": "翻译",
     "content": "请将以下中文翻译成地道、流畅的英文：\n\n[粘贴文本]"},
    {"name": "英译中", "category": "翻译",
     "content": "请将以下英文翻译成流畅、自然的中文：\n\n[粘贴文本]"},
    {"name": "今日计划", "category": "效率",
     "content": "今天是 [日期]，请帮我规划今天的工作任务：\n\n待办：\n- [任务1]\n- [任务2]\n\n请按优先级排序并给出时间分配建议。"},
    {"name": "周报草稿", "category": "效率",
     "content": "请帮我撰写本周工作周报草稿：\n\n本周完成：\n- [工作1]\n\n下周计划：\n- [计划1]\n\n请整理成标准周报格式。"},
    {"name": "头脑风暴", "category": "效率",
     "content": "请围绕以下主题进行头脑风暴，提供 10 个创意想法：\n\n主题：[输入主题]"},
]


async def _seed_builtin_templates(db) -> None:
    """首次启动时写入内置模板。"""
    for i, t in enumerate(_BUILTIN_TEMPLATES):
        await db.create_template(
            name=t["name"],
            content=t["content"],
            category=t["category"],
            sort_order=i,
        )
    logger.info(f"已写入 {len(_BUILTIN_TEMPLATES)} 个内置提示词模板")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = AppConfig()
    logger.info(f"启动 Agent 系统，模型: {config.llm.default_model}")

    await init_db()
    db = get_db_manager()

    # 优先加载 Provider API Keys（写入 os.environ，LiteLLM 自动读取）
    from .providers.key_manager import apply_all_provider_keys
    await apply_all_provider_keys(db)

    agent = await AgentLoop.create(config, db)

    # 初始化 MCPManager，从数据库加载并连接已启用的 MCP 服务器
    from .tools.mcp_client import MCPManager
    mcp_manager = MCPManager(agent.tools)
    mcp_servers = await db.list_mcp_servers()
    for srv in mcp_servers:
        if srv.get("enabled"):
            await mcp_manager.connect(srv)

    # 从数据库加载默认模型配置（如果有，作为中优先级兜底）
    default_cfg = await db.get_default_model_config()
    if default_cfg:
        agent.model = default_cfg["model_id"]
        agent.temperature = default_cfg["temperature"]
        agent.max_tokens = default_cfg["max_tokens"]
        logger.info(f"已从数据库加载默认模型配置: {default_cfg['name']} ({default_cfg['model_id']})")

    # 从 global_settings 加载持久化的 LLM 运行参数（最高优先级，覆盖 .env 和 model_configs）
    _gs_model = await db.get_setting("llm_default_model", "")
    if _gs_model:
        agent.model = _gs_model
        logger.info(f"已从全局设置加载默认模型: {_gs_model}")
    for _key, _attr, _cast in [
        ("llm_max_tokens",            "max_tokens",                         int),
        ("llm_temperature",           "temperature",                        float),
        ("llm_max_iterations",        "max_iterations",                     int),
    ]:
        _val = await db.get_setting(_key, "")
        if _val:
            try:
                setattr(agent, _attr, _cast(_val))
            except (ValueError, TypeError):
                pass
    _ctx = await db.get_setting("llm_context_window_tokens", "")
    if _ctx:
        try:
            agent.memory.context_window_tokens = int(_ctx)
        except (ValueError, TypeError):
            pass

    # 启动定时任务调度器
    scheduler = AgentScheduler(agent, db)
    scheduler.start()
    await scheduler.load_tasks_from_db()

    # 将任务工具注册到 Agent（需在 scheduler 就绪后）
    from .tools.task_tools import register_task_tools
    register_task_tools(agent.tools, db, scheduler)

    # 注册 SubAgent 工具（需在 agent 完全就绪后注册，以便持有引用）
    from .tools.subagent import SpawnSubAgentsTool
    agent.tools.register(SpawnSubAgentsTool(agent))

    # 从 DB 加载全局禁用工具集合
    import json as _json
    disabled_raw = await db.get_setting("disabled_tools", "[]")
    try:
        disabled_set = set(_json.loads(disabled_raw))
    except Exception:
        disabled_set = set()
    agent.tools.set_globally_disabled(disabled_set)
    if disabled_set:
        logger.info(f"已从数据库加载全局禁用工具: {disabled_set}")

    # 内置提示词模板（首次启动种子）
    existing = await db.list_templates()
    if not existing:
        await _seed_builtin_templates(db)

    # 首次启动种子注入默认 Provider + 模型列表
    await _seed_default_providers(db)

    app.state.agent = agent
    app.state.config = config
    app.state.scheduler = scheduler
    app.state.mcp_manager = mcp_manager

    logger.info("Agent 系统启动完成")
    yield

    await mcp_manager.close_all()
    await scheduler.stop()
    await close_db()
    logger.info("Agent 系统已关闭")


app = FastAPI(title="My Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# 生产环境：挂载 Vue 构建产物
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
