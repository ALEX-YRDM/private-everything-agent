from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from loguru import logger

from .config import AppConfig
from .database import init_db, close_db, get_db_manager
from .agent.loop import AgentLoop
from .api.routes import router as api_router
from .api.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = AppConfig()
    logger.info(f"启动 Agent 系统，模型: {config.llm.default_model}")

    await init_db()
    db = get_db_manager()
    agent = await AgentLoop.create(config, db)

    app.state.agent = agent
    app.state.config = config

    logger.info("Agent 系统启动完成")
    yield

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
