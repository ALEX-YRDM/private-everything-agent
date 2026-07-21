import asyncio
import os
import signal as _signal
import uuid
from collections import deque
from pathlib import Path
from .base import Tool
from .context import ToolContext


class ExecTool(Tool):
    name = "exec"
    description = (
        "在 shell 中执行命令，返回 stdout + stderr（**需用户确认**）。"
        "默认 cwd = 会话工作目录，可通过 cwd 参数覆盖。"
        "对长时任务（dev server、tail -f、pytest -x 全量跑）用 spawn_background 而不是 exec。"
        "示例：{command:'npm test', timeout:180}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认取会话配置（一般 30）；跑测试/构建可显式设 120-600。上限 1800。",
            },
            "cwd": {"type": "string", "description": "工作目录，默认为当前会话工作目录"},
        },
        "required": ["command"],
    }

    def __init__(self, default_cwd: Path, timeout: int = 30):
        # default_cwd 供无 ctx 的兜底调用（如启动脚本、定时任务未设 working_dir）
        self.default_cwd = default_cwd
        self.default_timeout = timeout

    async def execute(self, command: str, timeout: int = None, cwd: str = None,
                      _ctx: ToolContext | None = None) -> str:
        timeout = timeout or self.default_timeout
        # 硬上限：即便用户传超大值也 clamp 到 30 分钟，避免连接被挂太久
        timeout = min(max(int(timeout), 1), 1800)
        # 优先级：显式 cwd 参数 > ctx.cwd > default_cwd
        effective_cwd = cwd or (str(_ctx.cwd) if _ctx else str(self.default_cwd))
        proc = None
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")
            result = ""
            if output:
                result += f"STDOUT:\n{output}"
            if error:
                result += f"\nSTDERR:\n{error}"
            result += f"\n[退出码: {proc.returncode}]"
            return result.strip()
        except asyncio.TimeoutError:
            # 修复：超时后 kill 进程，避免僵尸
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            return f"[超时] 命令执行超过 {timeout} 秒（已终止进程）。如需长时运行请改用 spawn_background。"


# ─── 后台进程管理 ─────────────────────────────────────────────────────────
# 全局注册表：进程 id → 元数据 + rolling stdout/stderr buffer
_BG_PROCS: dict[str, dict] = {}
_BG_LOCK = asyncio.Lock()
_BG_BUF_MAXLINES = 2000   # 每个进程 rolling buffer 最多留最近 N 行


async def _pump_stream(pid_key: str, stream, which: str):
    """把进程的 stdout/stderr 读到 rolling buffer。"""
    while True:
        line = await stream.readline()
        if not line:
            break
        entry = _BG_PROCS.get(pid_key)
        if entry is None:
            break
        buf: deque = entry[which]
        buf.append(line.decode("utf-8", errors="replace"))


class SpawnBackgroundTool(Tool):
    name = "spawn_background"
    description = (
        "启动一个后台进程（不阻塞、不等待完成），返回 process_id 便于后续用 "
        "read_process_output / kill_process 交互。适用场景：启动 dev server、"
        "跑长时测试、观察日志。**需用户确认**。"
        "示例：{command:'npm run dev', cwd:'.'} 或 {command:'tail -f /tmp/x.log'}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要在后台执行的 shell 命令"},
            "cwd": {"type": "string", "description": "工作目录，默认为当前会话工作目录"},
            "label": {"type": "string", "description": "可读标签，便于识别（默认取命令首词）"},
        },
        "required": ["command"],
    }

    def __init__(self, default_cwd: Path):
        self.default_cwd = default_cwd

    async def execute(self, command: str, cwd: str = None, label: str = None,
                      _ctx: ToolContext | None = None) -> str:
        effective_cwd = cwd or (str(_ctx.cwd) if _ctx else str(self.default_cwd))
        pid_key = f"bg-{uuid.uuid4().hex[:8]}"
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=effective_cwd,
            start_new_session=True,   # 独立进程组，便于 kill_process 整组终结
        )
        entry = {
            "pid": proc.pid,
            "proc": proc,
            "command": command,
            "cwd": effective_cwd,
            "label": label or (command.split() or ["proc"])[0],
            "stdout": deque(maxlen=_BG_BUF_MAXLINES),
            "stderr": deque(maxlen=_BG_BUF_MAXLINES),
        }
        async with _BG_LOCK:
            _BG_PROCS[pid_key] = entry
        # 后台 pump 两个流；创建任务但不 await
        entry["stdout_task"] = asyncio.create_task(_pump_stream(pid_key, proc.stdout, "stdout"))
        entry["stderr_task"] = asyncio.create_task(_pump_stream(pid_key, proc.stderr, "stderr"))
        return (
            f"已启动后台进程：{pid_key}\n"
            f"pid={proc.pid}  label={entry['label']}\n"
            f"命令：{command}\n"
            f"工作目录：{effective_cwd}\n\n"
            f"用 read_process_output(process_id='{pid_key}') 查看输出，"
            f"kill_process(process_id='{pid_key}') 终止。"
        )


class ReadProcessOutputTool(Tool):
    name = "read_process_output"
    description = (
        "读取后台进程当前累计的 stdout/stderr（默认返回最近 200 行）。"
        "还会附带进程当前状态（running / exited）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "process_id": {"type": "string", "description": "spawn_background 返回的 process_id"},
            "tail_lines": {"type": "integer", "description": "返回最近 N 行，默认 200，最大 1000"},
        },
        "required": ["process_id"],
    }

    async def execute(self, process_id: str, tail_lines: int = 200) -> str:
        entry = _BG_PROCS.get(process_id)
        if not entry:
            return f"[错误] 未找到后台进程 {process_id}"
        tail_lines = min(max(int(tail_lines or 200), 1), 1000)
        proc = entry["proc"]
        status = "running" if proc.returncode is None else f"exited (code={proc.returncode})"
        stdout_tail = "".join(list(entry["stdout"])[-tail_lines:])
        stderr_tail = "".join(list(entry["stderr"])[-tail_lines:])
        out = [
            f"[{process_id}] status={status} label={entry['label']} pid={entry['pid']}",
            f"命令：{entry['command']}",
        ]
        if stdout_tail:
            out.append(f"\n--- STDOUT (最近 {tail_lines} 行) ---\n{stdout_tail}")
        if stderr_tail:
            out.append(f"\n--- STDERR (最近 {tail_lines} 行) ---\n{stderr_tail}")
        if not stdout_tail and not stderr_tail:
            out.append("\n(还没有输出)")
        return "\n".join(out)


class KillProcessTool(Tool):
    name = "kill_process"
    description = (
        "终止 spawn_background 启动的后台进程（发 SIGTERM，10 秒不退则 SIGKILL）。"
        "已 exited 的进程会保留 buffer 供读取，直到 forget_process。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "process_id": {"type": "string", "description": "process_id"},
        },
        "required": ["process_id"],
    }

    async def execute(self, process_id: str) -> str:
        entry = _BG_PROCS.get(process_id)
        if not entry:
            return f"[错误] 未找到后台进程 {process_id}"
        proc = entry["proc"]
        if proc.returncode is not None:
            return f"[已结束] {process_id} 早已退出，code={proc.returncode}"
        try:
            os.killpg(os.getpgid(proc.pid), _signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except asyncio.TimeoutError:
            try:
                os.killpg(os.getpgid(proc.pid), _signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                return f"[警告] {process_id} 无法终止（可能已成孤儿），code=?"
        return f"[已终止] {process_id}, exit code={proc.returncode}"


class ListProcessesTool(Tool):
    name = "list_processes"
    description = "列出当前所有后台进程（spawn_background 启动的），显示状态和标签。"
    parameters = {"type": "object", "properties": {}}

    async def execute(self) -> str:
        if not _BG_PROCS:
            return "(无后台进程)"
        rows = []
        for pk, entry in _BG_PROCS.items():
            proc = entry["proc"]
            status = "running" if proc.returncode is None else f"exited({proc.returncode})"
            rows.append(f"{pk}  [{status}]  {entry['label']}  pid={entry['pid']}  cmd={entry['command']}")
        return "\n".join(rows)
