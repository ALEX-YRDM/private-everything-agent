from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..deps import get_db

router = APIRouter(prefix="/templates", tags=["templates"])


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


@router.get("")
async def list_templates(db=Depends(get_db)):
    return {"templates": await db.list_templates()}


@router.post("")
async def create_template(body: TemplateCreate, db=Depends(get_db)):
    return await db.create_template(
        name=body.name,
        content=body.content,
        category=body.category,
        sort_order=body.sort_order,
    )


@router.put("/{tpl_id}")
async def update_template(tpl_id: int, body: TemplateUpdate, db=Depends(get_db)):
    updates = body.model_dump(exclude_none=True)
    tpl = await db.update_template(tpl_id, **updates)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return tpl


@router.delete("/{tpl_id}")
async def delete_template(tpl_id: int, db=Depends(get_db)):
    ok = await db.delete_template(tpl_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"ok": True}