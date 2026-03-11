from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: str = "新会话"
    model: str | None = None


class UpdateTitleRequest(BaseModel):
    title: str


@router.get("/sessions")
async def list_sessions(request: Request):
    """列出所有会话。"""
    agent = request.app.state.agent
    sessions = await agent.sessions.list_sessions()
    return {"sessions": sessions}


@router.post("/sessions")
async def create_session(request: Request, body: CreateSessionRequest):
    """创建新会话。"""
    agent = request.app.state.agent
    session = await agent.sessions.create_session(title=body.title, model=body.model)
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    """删除会话。"""
    agent = request.app.state.agent
    ok = await agent.sessions.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
async def get_messages(request: Request, session_id: str):
    """获取会话的历史消息（用于前端展示）。"""
    agent = request.app.state.agent
    session = await agent.sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = await agent.sessions.get_messages_for_display(session_id)
    return {"messages": messages}


@router.put("/sessions/{session_id}/title")
async def update_title(request: Request, session_id: str, body: UpdateTitleRequest):
    """修改会话标题。"""
    agent = request.app.state.agent
    ok = await agent.sessions.update_title(session_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.get("/models")
async def list_models():
    """列出支持的模型。"""
    models = [
        {"id": "gpt-4o", "provider": "OpenAI"},
        {"id": "gpt-4o-mini", "provider": "OpenAI"},
        {"id": "o1", "provider": "OpenAI"},
        {"id": "o3-mini", "provider": "OpenAI"},
        {"id": "claude-3-5-sonnet-20241022", "provider": "Anthropic"},
        {"id": "claude-3-7-sonnet-20250219", "provider": "Anthropic"},
        {"id": "deepseek/deepseek-chat", "provider": "DeepSeek"},
        {"id": "deepseek/deepseek-reasoner", "provider": "DeepSeek"},
        {"id": "gemini/gemini-2.0-flash", "provider": "Google"},
        {"id": "gemini/gemini-2.5-pro", "provider": "Google"},
        {"id": "dashscope/qwen-max", "provider": "阿里云"},
        {"id": "moonshot/moonshot-v1-128k", "provider": "Kimi"},
        {"id": "ollama/qwen2.5:14b", "provider": "Ollama（本地）"},
        {"id": "ollama/llama3.3:70b", "provider": "Ollama（本地）"},
    ]
    return {"models": models}


@router.get("/tools")
async def list_tools(request: Request):
    """列出已注册的工具。"""
    agent = request.app.state.agent
    tools = agent.tools.list_tools()
    return {"tools": tools}


@router.get("/config")
async def get_config(request: Request):
    """获取当前配置（不含敏感信息）。"""
    config = request.app.state.config
    return {
        "model": config.llm.default_model,
        "max_tokens": config.llm.max_tokens,
        "temperature": config.llm.temperature,
        "max_iterations": config.llm.max_iterations,
        "workspace": config.workspace,
        "restrict_to_workspace": config.tools.restrict_to_workspace,
        "mcp_servers": [{"name": s.name, "transport": s.transport} for s in config.mcp_servers],
    }


@router.put("/config/model")
async def update_model(request: Request, body: dict):
    """切换当前使用的模型。"""
    agent = request.app.state.agent
    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="缺少 model 参数")
    agent.model = model
    return {"ok": True, "model": model}
