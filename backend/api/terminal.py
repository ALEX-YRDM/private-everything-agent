"""
本地终端 WebSocket 端点：把 Unix pty 的 stdin/stdout 双向桥接到浏览器 xterm.js。

设计要点：
- shell 默认取 $SHELL，否则 /bin/bash；cwd 默认 session.working_dir 或 $HOME
- 只做用户交互，不给 Agent 感知（这是本次约定的 Item 5 边界）
- pty master fd 用 loop.add_reader 无阻塞读取
- 客户端断开 → SIGTERM 子进程；进程退出 → 通知客户端 exit code
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import shutil
import signal
import struct
import termios
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


async def _get_working_dir(app_state, session_id: str) -> str:
    """从 session_manager 拿到 working_dir，否则用 $HOME"""
    try:
        sessions = getattr(app_state, "session_manager", None) or app_state.agent.sessions
        session = await sessions.get_session(session_id)
        if session and session.get("working_dir"):
            wd = session["working_dir"]
            if Path(wd).is_dir():
                return wd
    except Exception:
        pass
    return os.path.expanduser("~")


def _pick_shell() -> str:
    """挑一个可用的 shell：$SHELL > zsh > bash > sh"""
    for cand in (os.environ.get("SHELL"), "/bin/zsh", "/bin/bash", "/bin/sh"):
        if cand and Path(cand).exists() and shutil.which(cand):
            return cand
    return "/bin/sh"


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    """更新 pty 窗口大小 → 让 vim/less 知道自己有多大"""
    try:
        packed = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)
    except Exception:
        pass


@router.websocket("/ws/terminal/{session_id}")
async def terminal_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    cwd = await _get_working_dir(websocket.app.state, session_id)
    shell = _pick_shell()

    # fork pty
    pid, master_fd = pty.fork()
    if pid == 0:
        # 子进程：切目录 → exec shell（交互式登录）
        try:
            os.chdir(cwd)
        except Exception:
            os.chdir(os.path.expanduser("~"))
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        # 让 shell 走交互 + 登录，能读到用户的 rc 文件
        os.execvpe(shell, [shell, "-l", "-i"], env)
        # 不会到达

    # 父进程：把 fd 设为 non-blocking
    fl = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    loop = asyncio.get_running_loop()
    output_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def _on_readable():
        try:
            data = os.read(master_fd, 4096)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            # EIO 通常代表子进程已终止
            try:
                loop.remove_reader(master_fd)
            except Exception:
                pass
            output_queue.put_nowait(b"")  # 终止哨兵
            return
        if not data:
            try:
                loop.remove_reader(master_fd)
            except Exception:
                pass
            output_queue.put_nowait(b"")
            return
        output_queue.put_nowait(data)

    loop.add_reader(master_fd, _on_readable)

    # 初始 hello，告诉前端 shell 已就绪
    try:
        await websocket.send_text(json.dumps({
            "type": "ready", "cwd": cwd, "shell": shell,
        }))
    except Exception:
        pass

    async def _pump_output():
        """把 pty 的输出发送给客户端"""
        while True:
            data = await output_queue.get()
            if not data:  # 终止哨兵
                break
            try:
                await websocket.send_text(json.dumps({
                    "type": "output", "data": data.decode("utf-8", errors="replace"),
                }))
            except Exception:
                break

    async def _pump_input():
        """从客户端读命令 / 事件，写到 pty"""
        while True:
            try:
                msg = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            try:
                obj = json.loads(msg)
            except Exception:
                continue
            t = obj.get("type")
            if t == "input":
                data = obj.get("data", "")
                if isinstance(data, str) and data:
                    try:
                        os.write(master_fd, data.encode("utf-8"))
                    except OSError:
                        break
            elif t == "resize":
                rows = int(obj.get("rows", 24) or 24)
                cols = int(obj.get("cols", 80) or 80)
                _set_winsize(master_fd, rows, cols)
            elif t == "signal":
                sig = obj.get("name", "INT")
                sig_map = {"INT": signal.SIGINT, "TERM": signal.SIGTERM,
                           "QUIT": signal.SIGQUIT, "KILL": signal.SIGKILL}
                try:
                    os.killpg(os.getpgid(pid), sig_map.get(sig, signal.SIGINT))
                except Exception:
                    pass

    out_task = asyncio.create_task(_pump_output())
    in_task = asyncio.create_task(_pump_input())

    try:
        # 任一 pump 结束即结束整个连接
        done, pending = await asyncio.wait(
            [out_task, in_task], return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
    except Exception as e:
        logger.warning(f"terminal ws error session={session_id}: {e}")
    finally:
        try:
            loop.remove_reader(master_fd)
        except Exception:
            pass
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            pass
        try:
            os.close(master_fd)
        except Exception:
            pass
        # 通知客户端退出（若 socket 还开着）
        try:
            _, status = os.waitpid(pid, os.WNOHANG)
            code = os.WEXITSTATUS(status) if status else 0
            await websocket.send_text(json.dumps({"type": "exit", "code": code}))
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
