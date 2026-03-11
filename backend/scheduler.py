"""
定时任务调度器（基于 APScheduler + asyncio）。

支持两种触发格式：
  - 标准 5 字段 cron：  "0 8 * * *"  (分 时 日 月 周)
  - 间隔格式：          "@every 30s" / "@every 5m" / "@every 2h"
"""
import asyncio
import re
from datetime import datetime
from loguru import logger

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APScheduler_AVAILABLE = True
except ImportError:
    APScheduler_AVAILABLE = False
    logger.warning("apscheduler 未安装，定时任务功能不可用。运行: pip install apscheduler")


# ── 解析调度表达式 ──────────────────────────────────────────────────────────

_INTERVAL_RE = re.compile(r"^@every\s+(\d+)(s|sec|m|min|h|hr)$", re.IGNORECASE)


def parse_trigger(expr: str):
    """
    将调度表达式解析为 APScheduler trigger。

    支持格式：
      "@every 30s"   → IntervalTrigger(seconds=30)
      "@every 5m"    → IntervalTrigger(minutes=5)
      "@every 2h"    → IntervalTrigger(hours=2)
      "0 8 * * *"    → CronTrigger(minute=0, hour=8, ...)
    """
    expr = expr.strip()

    # 间隔格式
    m = _INTERVAL_RE.match(expr)
    if m:
        value = int(m.group(1))
        unit = m.group(2).lower()
        if unit in ("s", "sec"):
            return IntervalTrigger(seconds=value)
        elif unit in ("m", "min"):
            return IntervalTrigger(minutes=value)
        elif unit in ("h", "hr"):
            return IntervalTrigger(hours=value)

    # 标准 cron（5字段）
    parts = expr.split()
    if len(parts) == 5:
        return CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone="Asia/Shanghai",
        )

    raise ValueError(
        f"不支持的调度表达式: '{expr}'。"
        "支持格式：5字段cron（'0 8 * * *'）或间隔('@every 30s'/'@every 5m'/'@every 2h')"
    )


def validate_expr(expr: str) -> str | None:
    """返回错误描述，None 表示合法。"""
    try:
        parse_trigger(expr)
        return None
    except Exception as e:
        return str(e)


def describe_expr(expr: str) -> str:
    """生成人类可读描述。"""
    expr = expr.strip()
    m = _INTERVAL_RE.match(expr)
    if m:
        value, unit = m.group(1), m.group(2).lower()
        label = {"s": "秒", "sec": "秒", "m": "分钟", "min": "分钟", "h": "小时", "hr": "小时"}
        return f"每 {value} {label.get(unit, unit)}"

    mapping = {
        "0 8 * * *":    "每天 08:00",
        "0 9 * * *":    "每天 09:00",
        "0 12 * * *":   "每天 12:00",
        "0 18 * * *":   "每天 18:00",
        "0 21 * * *":   "每天 21:00",
        "0 0 * * *":    "每天 00:00",
        "0 9 * * 1":    "每周一 09:00",
        "0 9 * * 5":    "每周五 09:00",
        "*/30 * * * *": "每30分钟",
        "0,30 * * * *": "每30分钟",
        "0 * * * *":    "每小时整点",
    }
    return mapping.get(expr, expr)


# ── 调度器主类 ──────────────────────────────────────────────────────────────

class AgentScheduler:
    """封装 APScheduler，管理所有定时 Agent 任务。"""

    def __init__(self, agent, db_manager):
        self.agent = agent
        self.db = db_manager
        self._scheduler: "AsyncIOScheduler | None" = None

    def start(self):
        if not APScheduler_AVAILABLE:
            return
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._scheduler.start()
        logger.info("定时任务调度器已启动（时区: Asia/Shanghai）")

    async def stop(self):
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("定时任务调度器已停止")

    async def load_tasks_from_db(self):
        """应用启动后从数据库加载所有启用的任务。"""
        if not self._scheduler:
            return
        tasks = await self.db.list_tasks()
        count = 0
        for task in tasks:
            if task.get("enabled"):
                self.add_task(task)
                count += 1
        logger.info(f"加载了 {count} 个定时任务")

    def add_task(self, task: dict):
        """注册一个任务到调度器。"""
        if not self._scheduler:
            return
        job_id = f"task_{task['id']}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        if not task.get("enabled"):
            return

        try:
            trigger = parse_trigger(task["cron_expr"])
            self._scheduler.add_job(
                self.run_task,
                trigger=trigger,
                args=[task["id"]],  # 只传 ID，执行时重新从 DB 读取
                id=job_id,
                name=task["name"],
                replace_existing=True,
            )
            desc = describe_expr(task["cron_expr"])
            logger.info(f"任务 [{task['name']}] 已调度：{desc}")
        except Exception as e:
            logger.error(f"任务 [{task['name']}] 调度失败: {e}")

    def reschedule_task(self, task: dict):
        self.add_task(task)

    def remove_task(self, task_id: int):
        if not self._scheduler:
            return
        job_id = f"task_{task_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            logger.info(f"任务 #{task_id} 已从调度器移除")

    async def run_task(self, task_id: int):
        """
        执行一次定时任务。
        - 每次从 DB 重新读取最新状态（保证 session_id 最新）
        - 任务的 model_id 通过参数传入 process_stream，不修改全局 agent.model
        - 完成后通过 WebSocket 广播通知所有连接的前端
        """
        from .api.connection_manager import manager as ws_manager

        task = await self.db.get_task(task_id)
        if not task:
            logger.warning(f"定时任务 #{task_id} 在数据库中不存在，跳过")
            return
        if not task.get("enabled"):
            logger.info(f"定时任务 [{task['name']}] 已禁用，跳过")
            return

        task_name = task["name"]
        session_id: str | None = None
        logger.info(f"开始执行定时任务 [{task_name}]（#{task_id}）")

        try:
            session_id = await self._get_or_create_session(task)
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            full_prompt = f"[定时任务: {task_name} | {now}]\n\n{task['prompt']}"

            # 使用 process_stream 的 model 参数覆盖，不修改全局 agent.model
            final_content = ""
            async for event in self.agent.process_stream(
                session_id, full_prompt, model=task.get("model_id") or None
            ):
                if event.get("type") == "content_delta":
                    final_content += event.get("content", "")
                elif event.get("type") == "done":
                    final_content = event.get("content") or final_content

            await self.db.update_task_run_status(task_id, "success", session_id)
            logger.info(f"定时任务 [{task_name}] 完成，会话: {session_id[:8]}...")

            await ws_manager.broadcast({
                "type": "task_notification",
                "task_id": task_id,
                "task_name": task_name,
                "status": "success",
                "session_id": session_id,
                "message": f"定时任务「{task_name}」已完成",
            })

        except Exception as e:
            err_msg = str(e)[:100]
            logger.error(f"定时任务 [{task_name}] 失败: {e}")
            await self.db.update_task_run_status(task_id, f"error: {err_msg}", session_id)

            await ws_manager.broadcast({
                "type": "task_notification",
                "task_id": task_id,
                "task_name": task_name,
                "status": "error",
                "session_id": session_id,
                "message": f"定时任务「{task_name}」执行失败: {err_msg}",
            })

    async def _get_or_create_session(self, task: dict) -> str:
        """
        获取或创建任务专属会话。
        同一任务始终复用同一会话，不重复创建。
        """
        # 先检查 DB 中记录的 session_id 是否仍有效
        if task.get("session_id"):
            existing = await self.db.fetch_one(
                "SELECT id FROM sessions WHERE id = ?", (task["session_id"],)
            )
            if existing:
                return task["session_id"]

        # 创建新专属会话并立即将 session_id 写回数据库，
        # 这样下次执行时能通过 get_task 读到最新 session_id
        from .session.manager import SessionManager
        sm = SessionManager(self.db)
        session = await sm.create_session(title=f"⏰ {task['name']}")
        new_session_id = session["id"]

        await self.db.execute(
            "UPDATE scheduled_tasks SET session_id = ? WHERE id = ?",
            (new_session_id, task["id"]),
        )
        return new_session_id
