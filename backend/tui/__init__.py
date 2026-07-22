"""mengdie-tui：Textual 版 TUI 客户端。

usage:
    mengdie-tui                          # 连本机默认后端
    mengdie-tui --backend http://x:8000  # 指定后端
    mengdie-tui --spawn                  # 后端未启动时自动 spawn
    mengdie-tui --session <sid>          # 打开指定会话
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from textual.app import App

from .backend_probe import spawn_backend, wait_backend_ready
from .client import MengdieClient
from .screens.main import MainScreen


class MengdieApp(App):
    """TUI 顶层应用。"""

    TITLE = "梦蝶 · Mengdie TUI"
    SUB_TITLE = ""

    def __init__(self, client: MengdieClient, initial_session_id: str | None = None):
        super().__init__()
        self.client = client
        self.initial_session_id = initial_session_id

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self.client, self.initial_session_id))

    async def on_unmount(self) -> None:
        try:
            await self.client.close()
        except Exception:
            pass


async def _run(base_url: str, spawn: bool, session_id: str | None) -> int:
    client = MengdieClient(base_url=base_url)
    spawned = None

    # 探测后端
    if not await client.ping():
        if not spawn:
            print(
                f"❌ 后端 {base_url} 未响应。\n"
                f"   请先启动：uvicorn backend.main:app --port 8000\n"
                f"   或加 --spawn 让 TUI 自动启动一个",
                file=sys.stderr,
            )
            await client.close()
            return 2

        # 自动 spawn
        from urllib.parse import urlparse
        port = urlparse(base_url).port or 8000
        print(f"⏳ 自动启动后端 (port {port}) …", file=sys.stderr)
        spawned = spawn_backend(port=port, log_file=None)
        if not await wait_backend_ready(base_url, timeout=20.0):
            print("❌ 后端启动超时（20 秒）", file=sys.stderr)
            spawned.stop()
            await client.close()
            return 3
        print("✔ 后端已就绪", file=sys.stderr)

    # 启动 TUI
    app = MengdieApp(client, initial_session_id=session_id)
    try:
        await app.run_async()
    finally:
        if spawned is not None:
            spawned.stop()
        await client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mengdie-tui", description="梦蝶 TUI 客户端")
    parser.add_argument("--backend", default="http://localhost:8000",
                        help="后端地址（默认 http://localhost:8000）")
    parser.add_argument("--spawn", action="store_true",
                        help="后端未启动时自动 spawn uvicorn 子进程")
    parser.add_argument("--session", default=None,
                        help="打开指定 session_id（默认最近一个）")
    args = parser.parse_args(argv)

    try:
        return asyncio.run(_run(args.backend, args.spawn, args.session))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
