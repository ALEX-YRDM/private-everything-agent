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

# _DEFAULT_PROVIDERS = [
#     {
#         "provider": "openai",
#         "display_name": "OpenAI",
#         "api_base": None,
#         "models": [
#             {"id": "openai/gpt-4.1",       "label": "GPT-4.1",      "supports_vision": True},
#             {"id": "openai/gpt-4.1-mini",  "label": "GPT-4.1 Mini", "supports_vision": True},
#             {"id": "openai/gpt-4.1-nano",  "label": "GPT-4.1 Nano", "supports_vision": True},
#             {"id": "openai/o4-mini",       "label": "o4-mini",       "supports_vision": True},
#             {"id": "openai/o3",            "label": "o3",            "supports_vision": True},
#             {"id": "openai/o3-mini",       "label": "o3-mini",       "supports_vision": False},
#             {"id": "openai/gpt-4o",        "label": "GPT-4o",       "supports_vision": True},
#             {"id": "openai/gpt-4o-mini",   "label": "GPT-4o Mini",  "supports_vision": True},
#         ],
#     },
#     {
#         "provider": "anthropic",
#         "display_name": "Anthropic",
#         "api_base": None,
#         "models": [
#             {"id": "anthropic/claude-opus-4-20250514",    "label": "Claude Opus 4",   "supports_vision": True},
#             {"id": "anthropic/claude-sonnet-4-20250514",  "label": "Claude Sonnet 4", "supports_vision": True},
#             {"id": "anthropic/claude-3-7-sonnet-20250219","label": "Claude 3.7 Sonnet","supports_vision": True},
#             {"id": "anthropic/claude-3-5-haiku-20241022", "label": "Claude 3.5 Haiku","supports_vision": True},
#         ],
#     },
#     {
#         "provider": "gemini",
#         "display_name": "Google Gemini",
#         "api_base": None,
#         "models": [
#             {"id": "gemini/gemini-2.5-pro-preview-05-06","label": "Gemini 2.5 Pro",       "supports_vision": True},
#             {"id": "gemini/gemini-2.5-flash",            "label": "Gemini 2.5 Flash",      "supports_vision": True},
#             {"id": "gemini/gemini-2.0-flash",            "label": "Gemini 2.0 Flash",      "supports_vision": True},
#             {"id": "gemini/gemini-2.0-flash-lite",       "label": "Gemini 2.0 Flash Lite", "supports_vision": True},
#         ],
#     },
#     {
#         "provider": "deepseek",
#         "display_name": "DeepSeek",
#         "api_base": None,
#         "models": [
#             {"id": "deepseek/deepseek-chat",     "label": "DeepSeek V3",     "supports_vision": False},
#             {"id": "deepseek/deepseek-reasoner", "label": "DeepSeek R1",     "supports_vision": False},
#         ],
#     },
#     {
#         "provider": "xai",
#         "display_name": "xAI (Grok)",
#         "api_base": None,
#         "models": [
#             {"id": "xai/grok-3",       "label": "Grok 3",       "supports_vision": True},
#             {"id": "xai/grok-3-mini",  "label": "Grok 3 Mini",  "supports_vision": False},
#             {"id": "xai/grok-2-vision","label": "Grok 2 Vision", "supports_vision": True},
#         ],
#     },
#     {
#         "provider": "groq",
#         "display_name": "Groq",
#         "api_base": None,
#         "models": [
#             {"id": "groq/llama-3.3-70b-versatile", "label": "Llama 3.3 70B",      "supports_vision": False},
#             {"id": "groq/llama-3.2-90b-vision",    "label": "Llama 3.2 90B Vision","supports_vision": True},
#             {"id": "groq/llama-3.2-11b-vision",    "label": "Llama 3.2 11B Vision","supports_vision": True},
#             {"id": "groq/qwen-qwq-32b",            "label": "Qwen QwQ 32B",        "supports_vision": False},
#         ],
#     },
#     {
#         "provider": "mistral",
#         "display_name": "Mistral AI",
#         "api_base": None,
#         "models": [
#             {"id": "mistral/mistral-large-latest", "label": "Mistral Large", "supports_vision": True},
#             {"id": "mistral/mistral-small-latest", "label": "Mistral Small", "supports_vision": True},
#             {"id": "mistral/codestral-latest",     "label": "Codestral",     "supports_vision": False},
#         ],
#     },
#     {
#         "provider": "openrouter",
#         "display_name": "OpenRouter",
#         "api_base": None,
#         "models": [
#             {"id": "openrouter/google/gemini-2.5-flash",          "label": "Gemini 2.5 Flash",  "supports_vision": True},
#             {"id": "openrouter/anthropic/claude-sonnet-4",        "label": "Claude Sonnet 4",   "supports_vision": True},
#             {"id": "openrouter/meta-llama/llama-3.3-70b-instruct","label": "Llama 3.3 70B",     "supports_vision": False},
#             {"id": "openrouter/deepseek/deepseek-r1",             "label": "DeepSeek R1",       "supports_vision": False},
#         ],
#     },
#     {
#         "provider": "ollama",
#         "display_name": "Ollama (本地)",
#         "api_base": "http://localhost:11434",
#         "models": [
#             {"id": "ollama/llama3.3",        "label": "Llama 3.3",       "supports_vision": False},
#             {"id": "ollama/llava",           "label": "LLaVA",           "supports_vision": True},
#             {"id": "ollama/qwen2.5:32b",     "label": "Qwen 2.5 32B",   "supports_vision": False},
#             {"id": "ollama/deepseek-r1:14b", "label": "DeepSeek R1 14B", "supports_vision": False},
#         ],
#     },
#     {
#         "provider": "volcengine",
#         "display_name": "字节跳动 (火山引擎)",
#         "api_base": None,
#         "models": [
#             {"id": "volcengine/doubao-pro-32k",  "label": "Doubao Pro 32K",  "supports_vision": True},
#             {"id": "volcengine/doubao-lite-32k", "label": "Doubao Lite 32K", "supports_vision": False},
#         ],
#     },
#     {
#         "provider": "dashscope",
#         "display_name": "阿里云 (百炼/通义)",
#         "api_base": None,
#         "models": [
#             {"id": "dashscope/qwen-max",            "label": "Qwen Max",    "supports_vision": True},
#             {"id": "dashscope/qwen-plus",           "label": "Qwen Plus",   "supports_vision": True},
#             {"id": "dashscope/qwen-turbo",          "label": "Qwen Turbo",  "supports_vision": True},
#             {"id": "dashscope/qwq-32b",             "label": "QwQ 32B",     "supports_vision": False},
#         ],
#     },
#     {
#         "provider": "zai",
#         "display_name": "智谱 AI (GLM)",
#         "api_base": None,
#         "models": [
#             {"id": "zai/glm-4.7",  "label": "GLM-4.7",  "supports_vision": True},
#             {"id": "zai/glm-4.6",  "label": "GLM-4.6",  "supports_vision": True},
#         ],
#     },
# ]

_DEFAULT_PROVIDERS = [
    {
        "provider": "openai",
        "display_name": "OpenAI",
        "api_base": None,
        "models": [
            {"id": "openai/gpt-5.5-pro",       "label": "GPT-5.5 Pro",       "supports_vision": True},
            {"id": "openai/gpt-5.5",           "label": "GPT-5.5",           "supports_vision": True},
            {"id": "openai/gpt-5.5-thinking",  "label": "GPT-5.5 Thinking",  "supports_vision": True},
            {"id": "openai/gpt-5.4",           "label": "GPT-5.4",           "supports_vision": True},
            {"id": "openai/o4-mini",           "label": "o4-mini",           "supports_vision": True},
            {"id": "openai/gpt-4.1",           "label": "GPT-4.1",           "supports_vision": True},
        ],
    },
    {
        "provider": "anthropic",
        "display_name": "Anthropic",
        "api_base": None,
        "models": [
            {"id": "anthropic/claude-opus-4-7",   "label": "Claude Opus 4.7",   "supports_vision": True},
            {"id": "anthropic/claude-sonnet-4-6", "label": "Claude Sonnet 4.6", "supports_vision": True},
            {"id": "anthropic/claude-haiku-4-5",  "label": "Claude Haiku 4.5",  "supports_vision": True},
            {"id": "anthropic/claude-opus-4",     "label": "Claude Opus 4",     "supports_vision": True},
        ],
    },
    {
        "provider": "gemini",
        "display_name": "Google Gemini",
        "api_base": None,
        "models": [
            {"id": "gemini/gemini-3.1-pro-preview",       "label": "Gemini 3.1 Pro",        "supports_vision": True},
            {"id": "gemini/gemini-3-flash",               "label": "Gemini 3 Flash",        "supports_vision": True},
            {"id": "gemini/gemini-3-pro",               "label": "Gemini 3 Pro",        "supports_vision": True},
            {"id": "gemini/gemini-3.1-flash-lite-preview","label": "Gemini 3.1 Flash Lite", "supports_vision": True},
            {"id": "gemini/gemini-2.5-pro",               "label": "Gemini 2.5 Pro",        "supports_vision": True},
        ],
    },
    {
        "provider": "deepseek",
        "display_name": "DeepSeek",
        "api_base": None,
        "models": [
            {"id": "deepseek/deepseek-v4-pro",   "label": "DeepSeek V4 Pro",   "supports_vision": False},
            {"id": "deepseek/deepseek-v4-flash", "label": "DeepSeek V4 Flash", "supports_vision": False},
            {"id": "deepseek/deepseek-chat",     "label": "DeepSeek V3",       "supports_vision": False},
            {"id": "deepseek/deepseek-reasoner", "label": "DeepSeek R1",       "supports_vision": False},
        ],
    },
    {
        "provider": "xai",
        "display_name": "xAI (Grok)",
        "api_base": None,
        "models": [
            {"id": "xai/grok-4.20-reasoning",     "label": "Grok 4.20 Reasoning",     "supports_vision": True},
            {"id": "xai/grok-4.20-non-reasoning", "label": "Grok 4.20 Non-Reasoning", "supports_vision": True},
            {"id": "xai/grok-3",                  "label": "Grok 3",                  "supports_vision": True},
        ],
    },
    {
        "provider": "groq",
        "display_name": "Groq",
        "api_base": None,
        "models": [
            {"id": "groq/deepseek-v4-flash",       "label": "DeepSeek V4 Flash",  "supports_vision": False},
            {"id": "groq/llama-3.3-70b-versatile", "label": "Llama 3.3 70B",      "supports_vision": False},
            {"id": "groq/llama-3.2-90b-vision",    "label": "Llama 3.2 90B Vision","supports_vision": True},
        ],
    },
    {
        "provider": "mistral",
        "display_name": "Mistral AI",
        "api_base": None,
        "models": [
            {"id": "mistral/mistral-large-latest", "label": "Mistral Large", "supports_vision": True},
            {"id": "mistral/mistral-small-latest", "label": "Mistral Small", "supports_vision": True},
            {"id": "mistral/codestral-latest",     "label": "Codestral",     "supports_vision": False},
        ],
    },
    {
        "provider": "openrouter",
        "display_name": "OpenRouter",
        "api_base": None,
        "models": [
            {"id": "openrouter/openai/gpt-5.5-pro",               "label": "GPT-5.5 Pro",       "supports_vision": True},
            {"id": "openrouter/anthropic/claude-opus-4-7",        "label": "Claude Opus 4.7",   "supports_vision": True},
            {"id": "openrouter/google/gemini-3.1-pro-preview",    "label": "Gemini 3.1 Pro",    "supports_vision": True},
            {"id": "openrouter/deepseek/deepseek-v4-pro",         "label": "DeepSeek V4 Pro",   "supports_vision": False},
        ],
    },
    {
        "provider": "ollama",
        "display_name": "Ollama (本地)",
        "api_base": "http://localhost:11434",
        "models": [
            {"id": "ollama/deepseek-v4-flash", "label": "DeepSeek V4 Flash", "supports_vision": False},
            {"id": "ollama/qwen3.6:27b",       "label": "Qwen 3.6 27B",      "supports_vision": False},
            {"id": "ollama/llama3.3",          "label": "Llama 3.3",         "supports_vision": False},
            {"id": "ollama/llava",             "label": "LLaVA",             "supports_vision": True},
        ],
    },
    {
        "provider": "volcengine",
        "display_name": "字节跳动 (火山引擎)",
        "api_base": None,
        "models": [
            
            {"id": "volcengine/doubao-seed-2-0-pro-260215", "label": "Doubao Seed 2.0 pro", "supports_vision": True},
            {"id": "volcengine/doubao-seed-2-0-lite-260215", "label": "Doubao Seed 2.0 lite", "supports_vision": True},
            {"id": "volcengine/doubao-seed-2-0-mini-260215", "label": "Doubao Seed 2.0 mini", "supports_vision": True},
            {"id": "volcengine/doubao-seed-2-0-code-preview-260215", "label": "Doubao Seed 2.0 code", "supports_vision": True},
            {"id": "volcengine/doubao-seed-1-8-251228",  "label": "Doubao Seed 1.8",  "supports_vision": True},
        ],
    },
    {
        "provider": "dashscope",
        "display_name": "阿里云 (百炼/通义)",
        "api_base": None,
        "models": [
            {"id": "dashscope/qwen3.6-max-preview", "label": "Qwen 3.6 Max",  "supports_vision": True},
            {"id": "dashscope/qwen3.6-plus",        "label": "Qwen 3.6 Plus", "supports_vision": True},
            {"id": "dashscope/qwen3.6-flash",            "label": "Qwen 3.6 flash",      "supports_vision": True},
            {"id": "dashscope/qwen3.5-flash",            "label": "Qwen 3.5 flash",      "supports_vision": True},
            {"id": "dashscope/qwen3.5-plus",           "label": "Qwen 3.5 plus",     "supports_vision": True},
            {"id": "dashscope/deepseek-v4-pro",           "label": "deepseek v4 pro",     "supports_vision": False},
            {"id": "dashscope/deepseek-v4-flash",           "label": "deepseek v4 flash",     "supports_vision": False},
        ],
    },
    {
        "provider": "zai",
        "display_name": "智谱 AI (GLM)",
        "api_base": None,
        "models": [
            {"id": "zai/glm-5.1",  "label": "GLM-5.1",  "supports_vision": True},
            {"id": "zai/glm-5.0",  "label": "GLM-5.0",  "supports_vision": True},
            {"id": "zai/glm-4.7",  "label": "GLM-4.7",  "supports_vision": True},
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


_BUILTIN_TEMPLATES: list[dict] = []


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

    # 从 global_settings 加载持久化的 LLM 运行参数（覆盖 .env 默认值）
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
