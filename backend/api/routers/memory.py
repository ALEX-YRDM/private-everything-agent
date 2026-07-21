"""
记忆管理端点：
- GET  /api/memory                        读全局用户画像
- PUT  /api/memory                        覆写全局用户画像
- GET  /api/sessions/{id}/summary         读会话摘要
- PUT  /api/sessions/{id}/summary         覆写会话摘要
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_agent, get_db, get_sessions

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryBody(BaseModel):
    memory_md: str


@router.get("")
async def get_memory(db=Depends(get_db)):
    row = await db.get_global_memory()
    return {"memory_md": row.get("memory_md") or ""}


@router.put("")
async def set_memory(body: MemoryBody, db=Depends(get_db)):
    await db.save_global_memory(memory_md=body.memory_md)
    return {"memory_md": body.memory_md}
