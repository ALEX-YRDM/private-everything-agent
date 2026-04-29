"""
API 路由聚合入口。
各资源路由拆分到 api/routers/ 子模块中，此文件仅负责汇总注册。
"""
from fastapi import APIRouter

from .routers.sessions import router as sessions_router
from .routers.providers import router as providers_router
from .routers.models import router as models_router
from .routers.tools import router as tools_router
from .routers.tasks import router as tasks_router
from .routers.templates import router as templates_router
from .routers.mcp import router as mcp_router
from .routers.skills import router as skills_router

router = APIRouter()
for sub in [sessions_router, providers_router, models_router, tools_router,
            tasks_router, templates_router, mcp_router, skills_router]:
    router.include_router(sub)