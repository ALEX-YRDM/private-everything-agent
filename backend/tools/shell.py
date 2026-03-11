import asyncio
from pathlib import Path
from .base import Tool


class ExecTool(Tool):
    name = "exec"
    description = "在 shell 中执行命令，返回 stdout + stderr。"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 30", "default": 30},
            "cwd": {"type": "string", "description": "工作目录，默认为 workspace"},
        },
        "required": ["command"],
    }

    def __init__(self, workspace: Path, timeout: int = 30):
        self.workspace = workspace
        self.default_timeout = timeout

    async def execute(self, command: str, timeout: int = None, cwd: str = None) -> str:
        timeout = timeout or self.default_timeout
        cwd = cwd or str(self.workspace)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
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
            return f"[超时] 命令执行超过 {timeout} 秒"
