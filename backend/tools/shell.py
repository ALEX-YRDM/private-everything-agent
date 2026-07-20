import asyncio
from pathlib import Path
from .base import Tool
from .context import ToolContext


class ExecTool(Tool):
    name = "exec"
    description = (
        "在 shell 中执行命令，返回 stdout + stderr（**需用户确认**）。"
        "默认 cwd = 会话工作目录，可通过 cwd 参数覆盖。"
        "示例：{command:'npm test'} 或 {command:'ls -la', cwd:'/tmp'}。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 30", "default": 30},
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
            return f"[超时] 命令执行超过 {timeout} 秒（已终止进程）"
