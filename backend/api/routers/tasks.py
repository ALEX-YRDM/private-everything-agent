import asyncio
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..deps import get_db, get_scheduler

router = APIRouter(prefix="/tasks", tags=["tasks"])


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


def _validate_cron(expr: str):
    from ...scheduler import validate_expr
    err = validate_expr(expr)
    if err:
        raise HTTPException(status_code=400, detail=err)


@router.get("")
async def list_tasks(db=Depends(get_db)):
    return {"tasks": await db.list_tasks()}


@router.post("")
async def create_task(body: TaskCreate, db=Depends(get_db), scheduler=Depends(get_scheduler)):
    _validate_cron(body.cron_expr)
    task = await db.create_task(name=body.name, cron_expr=body.cron_expr, prompt=body.prompt, model_id=body.model_id)
    if scheduler:
        scheduler.add_task(task)
    return task


@router.put("/{task_id}")
async def update_task(task_id: int, body: TaskUpdate, db=Depends(get_db), scheduler=Depends(get_scheduler)):
    updates = body.model_dump(exclude_none=True)
    if "cron_expr" in updates:
        _validate_cron(updates["cron_expr"])
    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0
    task = await db.update_task(task_id, **updates)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if scheduler:
        scheduler.reschedule_task(task)
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: int, db=Depends(get_db), scheduler=Depends(get_scheduler)):
    if scheduler:
        scheduler.remove_task(task_id)
    ok = await db.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}


@router.post("/{task_id}/run")
async def run_task_now(task_id: int, db=Depends(get_db), scheduler=Depends(get_scheduler)):
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if scheduler:
        asyncio.create_task(scheduler.run_task(task_id))
    return {"ok": True, "message": "任务已触发，结果将保存到对应会话"}