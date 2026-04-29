from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..deps import get_agent, get_db

router = APIRouter(tags=["models"])


@router.get("/models")
async def list_models(db=Depends(get_db)):
    """列出支持的模型（从 provider_keys 表读取）。"""
    rows = await db.list_provider_keys()
    dynamic_models: list[dict] = []
    for row in rows:
        provider_name = row.get("display_name") or row.get("provider")
        for m in row.get("models", []):
            dynamic_models.append({
                "id": m.get("id"),
                "provider": provider_name,
                "label": m.get("label") or m.get("id"),
            })
    if dynamic_models:
        return {"models": dynamic_models}

    # 兼容内置 fallback
    fallback = [
        {"id": "openai/gpt-4o", "provider": "OpenAI", "label": "GPT-4o"},
        {"id": "anthropic/claude-3-5-sonnet-20241022", "provider": "Anthropic", "label": "Claude 3.5 Sonnet"},
        {"id": "deepseek/deepseek-chat", "provider": "DeepSeek", "label": "DeepSeek Chat"},
        {"id": "gemini/gemini-2.0-flash", "provider": "Google", "label": "Gemini 2.0 Flash"},
    ]
    return {"models": fallback}


@router.post("/models/switch")
async def switch_model(body: dict, agent=Depends(get_agent), db=Depends(get_db)):
    """切换当前模型（全局生效）。"""
    from ...providers.key_manager import extract_provider, apply_provider_key
    model_id = body.get("model_id")
    if not model_id:
        raise HTTPException(status_code=400, detail="缺少 model_id")
    agent.model = model_id
    await db.set_setting("llm_default_model", model_id)
    provider = extract_provider(model_id)
    pk = await db.get_provider_key(provider)
    if pk:
        apply_provider_key(provider, pk.get("api_key"), pk.get("api_base"))
    return {"ok": True, "active_model": model_id, "provider": provider}


@router.post("/models/test")
async def test_model(body: dict):
    """校验指定模型是否可正常调用。"""
    import litellm
    from ...providers.litellm_provider import LiteLLMProvider
    model_id = body.get("model_id", "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="缺少 model_id")
    try:
        provider = LiteLLMProvider()
        kw = provider._build_kwargs(
            model_id,
            messages=[{"role": "user", "content": "1+1="}],
            max_tokens=1,
            stream=False,
        )
        await litellm.acompletion(**kw)
        return {"ok": True, "model_id": model_id}
    except Exception as e:
        return {"ok": False, "model_id": model_id, "error": str(e)}


# ── 全局配置 ────────────────────────────────────────────────────────────────


class LLMParamsUpdate(BaseModel):
    max_tokens: int | None = None
    temperature: float | None = None
    context_window_tokens: int | None = None
    max_iterations: int | None = None


@router.get("/config")
async def get_config(agent=Depends(get_agent)):
    return {
        "model": agent.model,
        "max_tokens": agent.max_tokens,
        "temperature": agent.temperature,
        "context_window_tokens": agent.memory.context_window_tokens,
        "max_iterations": agent.max_iterations,
        "workspace": str(agent.workspace),
    }


@router.put("/config/model")
async def update_model(body: dict, agent=Depends(get_agent), db=Depends(get_db)):
    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="缺少 model 参数")
    agent.model = model
    await db.set_setting("llm_default_model", model)
    return {"ok": True, "model": model}


@router.put("/config/llm")
async def update_llm_params(body: LLMParamsUpdate, agent=Depends(get_agent), db=Depends(get_db)):
    if body.max_tokens is not None:
        agent.max_tokens = body.max_tokens
        await db.set_setting("llm_max_tokens", str(body.max_tokens))
    if body.temperature is not None:
        agent.temperature = body.temperature
        await db.set_setting("llm_temperature", str(body.temperature))
    if body.context_window_tokens is not None:
        agent.memory.context_window_tokens = body.context_window_tokens
        await db.set_setting("llm_context_window_tokens", str(body.context_window_tokens))
    if body.max_iterations is not None:
        agent.max_iterations = body.max_iterations
        await db.set_setting("llm_max_iterations", str(body.max_iterations))
    return {
        "model": agent.model,
        "max_tokens": agent.max_tokens,
        "temperature": agent.temperature,
        "context_window_tokens": agent.memory.context_window_tokens,
        "max_iterations": agent.max_iterations,
    }