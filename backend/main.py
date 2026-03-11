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
