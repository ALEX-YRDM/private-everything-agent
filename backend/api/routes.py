from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

# ── Provider API Keys 相关 ──────────────────────────────────────────────────


class ProviderModel(BaseModel):
    id: str
    label: str


class ProviderKeyUpsert(BaseModel):
    provider: str
    display_name: str
    api_key: str | None = None
    api_base: str | None = None
    models: list[ProviderModel] | None = None  # None = 不更新模型列表


# ── 模型配置相关（简化版：无需每条单独存 API Key）─────────────────────────


class ModelConfigCreate(BaseModel):
    name: str
    model_id: str
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0.1
    max_tokens: int = 4096


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    model_id: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    enabled: bool | None = None


# ── 定时任务相关 ────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    name: str
    cron_expr: str
    prompt: str
    model_id: str | None = None


class TaskUpdate(BaseModel):
    name: str | None = None
    cron_expr: str | None = None
    prompt: str | None = None
    model_id: str | None = None
    enabled: bool | None = None


# ── Provider API Keys 接口 ──────────────────────────────────────────────────


@router.get("/provider-keys")
async def list_provider_keys(request: Request):
    """列出所有已保存的 Provider API Key 配置。"""
    db = request.app.state.agent.memory.db
    keys = await db.list_provider_keys()
    # 返回时隐藏 key 的中间部分
    result = []
    for k in keys:
        masked = _mask_key(k.get("api_key") or "")
        result.append({**k, "api_key_masked": masked, "api_key": masked if masked else None})
    return {"keys": result}


@router.post("/provider-keys")
async def upsert_provider_key(request: Request, body: ProviderKeyUpsert):
    """新增或更新 Provider（API Key + 模型列表）。models=None 时不更新模型列表。"""
    from ..providers.key_manager import apply_provider_key
    db = request.app.state.agent.memory.db
    models_list = [m.model_dump() for m in body.models] if body.models is not None else None
    row = await db.upsert_provider_key(
        provider=body.provider,
        display_name=body.display_name,
        api_key=body.api_key or None,
        api_base=body.api_base or None,
        models=models_list,
    )
    # 立即生效（仅在有新 key 时才更新环境变量）
    if body.api_key:
        apply_provider_key(body.provider, body.api_key, body.api_base or None)
    return {"ok": True, "row": row}


@router.put("/provider-keys/{provider}/models")
async def update_provider_models(request: Request, provider: str, body: list[ProviderModel]):
    """替换指定 provider 的模型列表（不影响 API Key）。"""
    db = request.app.state.agent.memory.db
    row = await db.update_provider_models(provider, [m.model_dump() for m in body])
    if not row:
        raise HTTPException(status_code=404, detail="Provider 不存在")
    return {"ok": True, "row": row}


@router.delete("/provider-keys/{provider}")
async def delete_provider_key(request: Request, provider: str):
    """删除指定 Provider 的 Key。"""
    db = request.app.state.agent.memory.db
    ok = await db.delete_provider_key(provider)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该 Provider 配置")
    return {"ok": True}


def _mask_key(key: str) -> str:
    """返回脱敏后的 key（保留前4位和后4位）。"""
    if not key or len(key) < 10:
        return "***" if key else ""
    return key[:4] + "****" + key[-4:]


# ── Session 相关 ─────────────────────────────────────────────────────────────


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


@router.get("/sessions/{session_id}/subagent-sessions")
async def get_subagent_sessions(request: Request, session_id: str):
    """获取某主会话下的所有 SubAgent 子会话。"""
    agent = request.app.state.agent
    sessions = await agent.sessions.get_subagent_sessions(session_id)
    return {"sessions": sessions}


@router.put("/sessions/{session_id}/title")
async def update_title(request: Request, session_id: str, body: UpdateTitleRequest):
    """修改会话标题。"""
    agent = request.app.state.agent
    ok = await agent.sessions.update_title(session_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


class SessionModelRequest(BaseModel):
    model: str | None = None  # None = 清除会话专属模型，恢复跟随全局


@router.put("/sessions/{session_id}/model")
async def set_session_model(request: Request, session_id: str, body: SessionModelRequest):
    """
    设置/清除会话专属模型（不影响全局默认模型）。
    兼容前端既可能传 {"model": "..."}，也可能传 {"model_id": "..."} 的情况。
    """
    agent = request.app.state.agent
    session = await agent.sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    model = body.model
    if model is None:
        # 兼容老的 / 不同实现的请求体
        raw = await request.json()
        model = raw.get("model_id")

    await agent.memory.db.execute(
        "UPDATE sessions SET model = ? WHERE id = ?",
        (model, session_id),
    )
    return {"session_id": session_id, "model": model}


@router.get("/models")
async def list_models(request: Request):
    """
    列出支持的模型。
    优先从 provider_keys 表中读取（包含自定义 Provider），
    如果为空则退回到内置静态列表，保证前端始终有可选项。
    """
    db = request.app.state.agent.memory.db
    rows = await db.list_provider_keys()
    dynamic_models: list[dict] = []
    for row in rows:
        provider_name = row.get("display_name") or row.get("provider")
        for m in row.get("models", []):
            dynamic_models.append(
                {
                    "id": m.get("id"),
                    "provider": provider_name,
                    "label": m.get("label") or m.get("id"),
                }
            )

    if dynamic_models:
        return {"models": dynamic_models}

    # 兼容：如果还没有 provider_keys 记录，则返回一份内置模型列表
    fallback = [
        {"id": "openai/gpt-4o", "provider": "OpenAI", "label": "GPT-4o"},
        {"id": "openai/gpt-4o-mini", "provider": "OpenAI", "label": "GPT-4o mini"},
        {"id": "openai/o1", "provider": "OpenAI", "label": "o1"},
        {"id": "openai/o3-mini", "provider": "OpenAI", "label": "o3-mini"},
        {"id": "anthropic/claude-3-5-sonnet-20241022", "provider": "Anthropic", "label": "Claude 3.5 Sonnet"},
        {"id": "anthropic/claude-3-7-sonnet-20250219", "provider": "Anthropic", "label": "Claude 3.7 Sonnet"},
        {"id": "deepseek/deepseek-chat", "provider": "DeepSeek", "label": "DeepSeek Chat"},
        {"id": "deepseek/deepseek-reasoner", "provider": "DeepSeek", "label": "DeepSeek Reasoner"},
        {"id": "gemini/gemini-2.0-flash", "provider": "Google", "label": "Gemini 2.0 Flash"},
        {"id": "gemini/gemini-2.5-pro", "provider": "Google", "label": "Gemini 2.5 Pro"},
        {"id": "dashscope/qwen-max", "provider": "阿里云", "label": "通义千问 Max"},
        {"id": "moonshot/moonshot-v1-128k", "provider": "Kimi", "label": "Moonshot v1 128K"},
        {"id": "ollama/qwen2.5:14b", "provider": "Ollama（本地）", "label": "Qwen 2.5 14B"},
        {"id": "ollama/llama3.3:70b", "provider": "Ollama（本地）", "label": "Llama 3.3 70B"},
    ]
    return {"models": fallback}


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


# ── 模型配置接口 ────────────────────────────────────────────────────────────


@router.get("/model-configs")
async def list_model_configs(request: Request):
    """列出所有已保存的模型配置。"""
    db = request.app.state.agent.memory.db
    configs = await db.list_model_configs()
    # 隐藏 api_key 明文（仅显示前4位）
    for c in configs:
        if c.get("api_key"):
            c["api_key_masked"] = c["api_key"][:4] + "****"
        else:
            c["api_key_masked"] = None
        c.pop("api_key", None)
    return {"configs": configs}


@router.post("/model-configs")
async def create_model_config(request: Request, body: ModelConfigCreate):
    """创建新的模型配置。"""
    db = request.app.state.agent.memory.db
    config = await db.create_model_config(
        name=body.name,
        model_id=body.model_id,
        api_key=body.api_key,
        api_base=body.api_base,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    return config


@router.put("/model-configs/{config_id}")
async def update_model_config(request: Request, config_id: int, body: ModelConfigUpdate):
    """更新模型配置。"""
    db = request.app.state.agent.memory.db
    updates = body.model_dump(exclude_none=True)
    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0
    config = await db.update_model_config(config_id, **updates)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return config


@router.delete("/model-configs/{config_id}")
async def delete_model_config(request: Request, config_id: int):
    """删除模型配置。"""
    db = request.app.state.agent.memory.db
    ok = await db.delete_model_config(config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"ok": True}


@router.post("/model-configs/{config_id}/activate")
async def activate_model_config(request: Request, config_id: int):
    """将指定配置设为默认并立即应用到 Agent（API Key 从 provider_keys 自动获取）。"""
    from ..providers.key_manager import extract_provider
    db = request.app.state.agent.memory.db
    config = await db.get_model_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    await db.set_default_model_config(config_id)

    agent = request.app.state.agent
    agent.model = config["model_id"]
    agent.temperature = config["temperature"]
    agent.max_tokens = config["max_tokens"]

    # 从 provider_keys 自动查找该模型对应的 API Key
    provider = extract_provider(config["model_id"])
    pk = await db.get_provider_key(provider)
    if pk:
        from ..providers.key_manager import apply_provider_key
        apply_provider_key(provider, pk.get("api_key"), pk.get("api_base"))

    return {"ok": True, "active_model": config["model_id"]}


@router.post("/models/switch")
async def switch_model(request: Request):
    """直接切换当前模型（全局生效，影响所有会话和定时任务）。"""
    from ..providers.key_manager import extract_provider
    body = await request.json()
    model_id = body.get("model_id")
    if not model_id:
        raise HTTPException(status_code=400, detail="缺少 model_id")

    agent = request.app.state.agent
    agent.model = model_id

    # 查找并应用对应 provider 的 Key
    db = agent.memory.db
    provider = extract_provider(model_id)
    pk = await db.get_provider_key(provider)
    if pk:
        from ..providers.key_manager import apply_provider_key
        apply_provider_key(provider, pk.get("api_key"), pk.get("api_base"))

    return {"ok": True, "active_model": model_id, "provider": provider}


@router.post("/models/test")
async def test_model(request: Request):
    """
    校验指定模型是否可正常调用（发送一条最小请求）。
    返回 {"ok": True} 或 {"ok": False, "error": "..."}，不会抛出 HTTP 错误。
    支持自定义 / OpenAI 兼容 Provider（使用 LiteLLMProvider 注入 api_key / api_base）。
    """
    import litellm
    from ..providers.litellm_provider import LiteLLMProvider
    body = await request.json()
    model_id = body.get("model_id", "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="缺少 model_id")

    try:
        provider = LiteLLMProvider()
        # 复用 LiteLLMProvider 的构造逻辑，从 key_manager 注册表中拿到 api_key / api_base
        kw = provider._build_kwargs(  # noqa: SLF001
            model_id,
            messages=[{"role": "user", "content": "1+1="}],
            max_tokens=1,
            stream=False,
        )
        await litellm.acompletion(**kw)
        return {"ok": True, "model_id": model_id}
    except Exception as e:
        return {"ok": False, "model_id": model_id, "error": str(e)}


# ── 定时任务接口 ────────────────────────────────────────────────────────────


@router.get("/tasks")
async def list_tasks(request: Request):
    """列出所有定时任务。"""
    db = request.app.state.agent.memory.db
    tasks = await db.list_tasks()
    return {"tasks": tasks}


@router.post("/tasks")
async def create_task(request: Request, body: TaskCreate):
    """创建定时任务。"""
    _validate_cron(body.cron_expr)
    db = request.app.state.agent.memory.db
    task = await db.create_task(
        name=body.name,
        cron_expr=body.cron_expr,
        prompt=body.prompt,
        model_id=body.model_id,
    )
    # 注册到调度器
    scheduler = request.app.state.scheduler
    if scheduler:
        scheduler.add_task(task)
    return task


@router.put("/tasks/{task_id}")
async def update_task(request: Request, task_id: int, body: TaskUpdate):
    """更新定时任务。"""
    db = request.app.state.agent.memory.db
    updates = body.model_dump(exclude_none=True)
    if "cron_expr" in updates:
        _validate_cron(updates["cron_expr"])
    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0
    task = await db.update_task(task_id, **updates)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    # 重新调度
    scheduler = request.app.state.scheduler
    if scheduler:
        scheduler.reschedule_task(task)
    return task


@router.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: int):
    """删除定时任务。"""
    db = request.app.state.agent.memory.db
    scheduler = request.app.state.scheduler
    if scheduler:
        scheduler.remove_task(task_id)
    ok = await db.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}


@router.post("/tasks/{task_id}/run")
async def run_task_now(request: Request, task_id: int):
    """立即手动触发一次定时任务。"""
    db = request.app.state.agent.memory.db
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    scheduler = request.app.state.scheduler
    if scheduler:
        import asyncio
        asyncio.create_task(scheduler.run_task(task_id))
    return {"ok": True, "message": "任务已触发，结果将保存到对应会话"}


def _validate_cron(expr: str):
    """验证调度表达式（支持5字段cron和@every格式）。"""
    from ..scheduler import validate_expr
    err = validate_expr(expr)
    if err:
        raise HTTPException(status_code=400, detail=err)


# ── 提示词模板接口 ───────────────────────────────────────────────────────────


class TemplateCreate(BaseModel):
    name: str
    content: str
    category: str = "通用"
    sort_order: int = 0


class TemplateUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    category: str | None = None
    sort_order: int | None = None


@router.get("/templates")
async def list_templates(request: Request):
    """列出所有提示词模板。"""
    db = request.app.state.agent.memory.db
    templates = await db.list_templates()
    return {"templates": templates}


@router.post("/templates")
async def create_template(request: Request, body: TemplateCreate):
    """创建提示词模板。"""
    db = request.app.state.agent.memory.db
    tpl = await db.create_template(
        name=body.name,
        content=body.content,
        category=body.category,
        sort_order=body.sort_order,
    )
    return tpl


@router.put("/templates/{tpl_id}")
async def update_template(request: Request, tpl_id: int, body: TemplateUpdate):
    """更新提示词模板。"""
    db = request.app.state.agent.memory.db
    updates = body.model_dump(exclude_none=True)
    tpl = await db.update_template(tpl_id, **updates)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return tpl


@router.delete("/templates/{tpl_id}")
async def delete_template(request: Request, tpl_id: int):
    """删除提示词模板。"""
    db = request.app.state.agent.memory.db
    ok = await db.delete_template(tpl_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"ok": True}


# ── 工具热插拔接口 ───────────────────────────────────────────────────────────


@router.get("/tools/state")
async def get_tool_states(request: Request, session_id: str | None = None):
    """
    获取所有工具的当前状态。
    session_id 可选：传入后同时返回该会话的 override 信息。
    """
    agent = request.app.state.agent
    session_overrides: dict[str, bool] = {}
    if session_id:
        meta = await agent.memory.db.get_session_metadata(session_id)
        session_overrides = meta.get("tool_overrides", {})
    states = agent.tools.get_tool_states(session_overrides=session_overrides)
    return {
        "tools": states,
        "globally_disabled": agent.tools.get_globally_disabled(),
        "session_overrides": session_overrides,
    }


@router.put("/tools/{tool_name}/global")
async def toggle_tool_global(request: Request, tool_name: str):
    """切换工具的全局启用/禁用状态（影响所有会话）。"""
    import json as _json
    agent = request.app.state.agent
    if tool_name not in agent.tools.list_tools():
        raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 不存在")
    new_enabled = agent.tools.toggle_global(tool_name)
    # 持久化到数据库
    disabled_list = agent.tools.get_globally_disabled()
    await agent.memory.db.set_setting("disabled_tools", _json.dumps(disabled_list))
    return {"tool": tool_name, "globally_enabled": new_enabled}


@router.put("/sessions/{session_id}/tool-overrides")
async def set_session_tool_overrides(request: Request, session_id: str):
    """
    设置/更新当前会话的工具 override。
    body: {"overrides": {"exec": false, "web_search": true}}
    传 null 表示清除该工具的 override（恢复跟随全局）。
    """
    agent = request.app.state.agent
    session = await agent.sessions.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    body = await request.json()
    new_overrides: dict[str, bool | None] = body.get("overrides", {})

    meta = await agent.memory.db.get_session_metadata(session_id)
    current_overrides: dict[str, bool] = meta.get("tool_overrides", {})

    for tool_name, value in new_overrides.items():
        if value is None:
            current_overrides.pop(tool_name, None)
        else:
            current_overrides[tool_name] = bool(value)

    meta["tool_overrides"] = current_overrides
    await agent.memory.db.set_session_metadata(session_id, meta)
    return {"session_id": session_id, "tool_overrides": current_overrides}


@router.get("/sessions/{session_id}/tool-overrides")
async def get_session_tool_overrides(request: Request, session_id: str):
    """获取会话的工具 override 配置。"""
    agent = request.app.state.agent
    meta = await agent.memory.db.get_session_metadata(session_id)
    return {
        "session_id": session_id,
        "tool_overrides": meta.get("tool_overrides", {}),
    }


# ── MCP 服务器管理接口 ────────────────────────────────────────────────────────


class MCPServerCreate(BaseModel):
    name: str
    display_name: str
    transport: str = "stdio"
    command: str = ""          # stdio: 可执行文件，如 "npx"
    args: list[str] = []       # stdio: 参数列表，如 ["-y", "xxx@latest"]
    url: str | None = None     # sse: 服务地址
    env: dict[str, str] = {}
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    display_name: str | None = None
    transport: str | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    enabled: bool | None = None


def _mcp_server_with_status(server: dict, request: Request) -> dict:
    """合并数据库配置 + 运行时连接状态。"""
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    if mcp_manager:
        status = mcp_manager.get_status(server["name"])
    else:
        status = {"status": "disconnected", "error_msg": None, "tools_count": 0}
    return {**server, **status}


@router.get("/mcp-servers")
async def list_mcp_servers(request: Request):
    """列出所有 MCP 服务器配置及当前连接状态。"""
    db = request.app.state.agent.memory.db
    servers = await db.list_mcp_servers()
    return {"servers": [_mcp_server_with_status(s, request) for s in servers]}


@router.post("/mcp-servers")
async def create_mcp_server(request: Request, body: MCPServerCreate):
    """新增 MCP 服务器配置，若 enabled=true 则立即尝试连接。"""
    db = request.app.state.agent.memory.db
    server = await db.create_mcp_server(
        name=body.name,
        display_name=body.display_name,
        transport=body.transport,
        command=body.command,
        args=body.args,
        url=body.url,
        env=body.env,
        enabled=body.enabled,
    )
    if body.enabled:
        mcp_manager = getattr(request.app.state, "mcp_manager", None)
        if mcp_manager:
            await mcp_manager.connect(server)
    return _mcp_server_with_status(server, request)


@router.put("/mcp-servers/{server_id}")
async def update_mcp_server(request: Request, server_id: int, body: MCPServerUpdate):
    """更新 MCP 服务器配置，若已连接则自动重连。"""
    db = request.app.state.agent.memory.db
    updates = body.model_dump(exclude_none=True)
    server = await db.update_mcp_server(server_id, **updates)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    if mcp_manager:
        if server.get("enabled"):
            await mcp_manager.reconnect(server)
        else:
            await mcp_manager.disconnect(server["name"])
    return _mcp_server_with_status(server, request)


@router.delete("/mcp-servers/{server_id}")
async def delete_mcp_server(request: Request, server_id: int):
    """删除 MCP 服务器配置，同时断开连接并注销其工具。"""
    db = request.app.state.agent.memory.db
    server = await db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    if mcp_manager:
        await mcp_manager.disconnect(server["name"])
    ok = await db.delete_mcp_server(server_id)
    if not ok:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    return {"ok": True}


@router.post("/mcp-servers/{server_id}/reconnect")
async def reconnect_mcp_server(request: Request, server_id: int):
    """手动重连指定 MCP 服务器。"""
    db = request.app.state.agent.memory.db
    server = await db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    if not mcp_manager:
        raise HTTPException(status_code=503, detail="MCP 管理器未初始化")
    success = await mcp_manager.reconnect(server)
    return _mcp_server_with_status(server, request) | {"reconnect_ok": success}


@router.post("/mcp-servers/{server_id}/toggle")
async def toggle_mcp_server(request: Request, server_id: int):
    """启用 / 禁用 MCP 服务器（同时连接或断开）。"""
    db = request.app.state.agent.memory.db
    server = await db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    new_enabled = not bool(server.get("enabled"))
    server = await db.update_mcp_server(server_id, enabled=new_enabled)
    mcp_manager = getattr(request.app.state, "mcp_manager", None)
    if mcp_manager:
        if new_enabled:
            await mcp_manager.connect(server)
        else:
            await mcp_manager.disconnect(server["name"])
    return _mcp_server_with_status(server, request)


# ── 系统技能管理 ────────────────────────────────────────────────────────────


@router.get("/skills/system")
async def list_system_skills(request: Request):
    """列出所有系统技能。"""
    skills_loader = request.app.state.agent.context.skills
    all_skills = skills_loader.list_system_skills(filter_unavailable=False)
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "available": skills_loader._check_requirements(s),
                "requires_bins": s.requires_bins,
                "requires_env": s.requires_env,
            }
            for s in all_skills
        ]
    }


@router.get("/skills/user")
async def list_user_skills(request: Request):
    """列出用户在 workspace/skills/ 中的自定义技能。"""
    skills_loader = request.app.state.agent.context.skills
    user_skills = skills_loader.list_user_skills()
    return {
        "skills": [
            {"name": s.name, "description": s.description, "path": str(s.path)}
            for s in user_skills
        ]
    }
