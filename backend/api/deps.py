"""
FastAPI 依赖注入：统一提供 agent / db / scheduler / mcp_manager 实例。
路由函数通过 Depends() 声明依赖，不再手动从 request.app.state 取值。
"""
from fastapi import Request

from ..agent.loop import AgentLoop
from ..database import DBManager
from ..session.manager import SessionManager


def get_agent(request: Request) -> AgentLoop:
    return request.app.state.agent


def get_db(request: Request) -> DBManager:
    return request.app.state.agent.memory.db


def get_sessions(request: Request) -> SessionManager:
    return request.app.state.agent.sessions


def get_scheduler(request: Request):
    return request.app.state.scheduler


def get_mcp_manager(request: Request):
    return getattr(request.app.state, "mcp_manager", None)