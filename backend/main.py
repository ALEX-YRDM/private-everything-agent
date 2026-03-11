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

    # 从数据库加载默认模型配置（如果有）
    default_cfg = await db.get_default_model_config()
    if default_cfg:
        agent.model = default_cfg["model_id"]
        agent.temperature = default_cfg["temperature"]
        agent.max_tokens = default_cfg["max_tokens"]
        logger.info(f"已从数据库加载默认模型配置: {default_cfg['name']} ({default_cfg['model_id']})")

    # 启动定时任务调度器
    scheduler = AgentScheduler(agent, db)
    scheduler.start()
    await scheduler.load_tasks_from_db()

    # 将任务工具注册到 Agent（需在 scheduler 就绪后）
    from .tools.task_tools import register_task_tools
    register_task_tools(agent.tools, db, scheduler)

    app.state.agent = agent
    app.state.config = config
    app.state.scheduler = scheduler

    logger.info("Agent 系统启动完成")
    yield

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
