from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..deps import get_db

router = APIRouter(prefix="/provider-keys", tags=["providers"])


class ProviderModel(BaseModel):
    id: str
    label: str
    supports_vision: bool | None = None
    context_window_tokens: int | None = None
    max_tokens: int | None = None


class ProviderKeyUpsert(BaseModel):
    provider: str
    display_name: str
    api_key: str | None = None
    api_base: str | None = None
    models: list[ProviderModel] | None = None


def _mask_key(key: str) -> str:
    """脱敏（保留前4位和后4位）。"""
    if not key or len(key) < 10:
        return "***" if key else ""
    return key[:4] + "****" + key[-4:]


@router.get("")
async def list_provider_keys(db=Depends(get_db)):
    keys = await db.list_provider_keys()
    result = []
    for k in keys:
        masked = _mask_key(k.get("api_key") or "")
        result.append({**k, "api_key_masked": masked, "api_key": masked if masked else None})
    return {"keys": result}


@router.post("")
async def upsert_provider_key(body: ProviderKeyUpsert, db=Depends(get_db)):
    from ...providers.key_manager import apply_provider_key
    models_list = [m.model_dump() for m in body.models] if body.models is not None else None
    row = await db.upsert_provider_key(
        provider=body.provider,
        display_name=body.display_name,
        api_key=body.api_key or None,
        api_base=body.api_base or None,
        models=models_list,
    )
    if body.api_key:
        apply_provider_key(body.provider, body.api_key, body.api_base or None)
    return {"ok": True, "row": row}


@router.put("/{provider}/models")
async def update_provider_models(provider: str, body: list[ProviderModel], db=Depends(get_db)):
    from ...providers.key_manager import register_model_params
    models_data = [m.model_dump() for m in body]
    row = await db.update_provider_models(provider, models_data)
    if not row:
        raise HTTPException(status_code=404, detail="Provider 不存在")
    register_model_params(models_data)
    return {"ok": True, "row": row}


@router.delete("/{provider}")
async def delete_provider_key(provider: str, db=Depends(get_db)):
    ok = await db.delete_provider_key(provider)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该 Provider 配置")
    return {"ok": True}