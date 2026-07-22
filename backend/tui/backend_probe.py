"""
检测 backend 是否就绪；未就绪时可选自动 spawn 一个 uvicorn 子进程。

设计目标：
- TUI 打开就能用；用户不用先手动 `uvicorn backend.main:app`
- 若 backend 已在跑（web UI 场景），复用现有的
- spawn 出来的子进程随 TUI 生命周期结束
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class SpawnedBackend:
    """spawn 出来的 backend 子进程句柄。"""
    process: subprocess.Popen
    port: int

    def stop(self) -> None:
        if self.process.poll() is None:
            try:
                # 发 SIGTERM，uvicorn 会 graceful shutdown
                if sys.platform == "win32":
                    self.process.terminate()
                else:
                    self.process.send_signal(signal.SIGTERM)
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            except Exception:
                # 子进程可能已经死了
                pass


async def wait_backend_ready(base_url: str, timeout: float = 15.0) -> bool:
    """轮询 /api/config，直到 200 或超时。"""
    import httpx
    end = asyncio.get_running_loop().time() + timeout
    async with httpx.AsyncClient(base_url=base_url, timeout=2.0) as client:
        while asyncio.get_running_loop().time() < end:
            try:
                r = await client.get("/api/config")
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
    return False


def spawn_backend(port: int = 8000, log_file: str | None = None) -> SpawnedBackend:
    """启动 uvicorn 子进程。stderr/stdout 重定向到 log_file 或 /dev/null 避免污染 TUI。"""
    # 优先用当前 venv 的 python，保证依赖一致
    python = sys.executable
    args = [
        python, "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", str(port),
    ]

    if log_file:
        stdout = open(log_file, "a", buffering=1, encoding="utf-8")
        stderr = subprocess.STDOUT
    else:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL

    # 独立进程组，方便统一 kill
    kwargs: dict = {"stdout": stdout, "stderr": stderr}
    if sys.platform != "win32":
        kwargs["preexec_fn"] = os.setsid

    proc = subprocess.Popen(args, **kwargs)
    return SpawnedBackend(process=proc, port=port)


def has_command(name: str) -> bool:
    """探测系统命令是否可用（供 /paste-img 等功能判断 pngpaste/xclip 之类）。"""
    return shutil.which(name) is not None


@contextlib.asynccontextmanager
async def spawned_backend_context(port: int = 8000, log_file: str | None = None):
    """with 语法自动清理 spawn 出来的子进程。"""
    handle = spawn_backend(port=port, log_file=log_file)
    try:
        yield handle
    finally:
        handle.stop()
