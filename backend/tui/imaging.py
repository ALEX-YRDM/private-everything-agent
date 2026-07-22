"""终端图片渲染：iTerm2 / kitty 内联协议。

- 探测：$TERM_PROGRAM / $TERM / $KITTY_WINDOW_ID
- iTerm2：ESC ] 1337 ; File = ... : <base64> BEL
- kitty：ESC _ G ... ; <base64> ESC \\
- 不支持则回退 ASCII 占位

同时提供剪贴板图片抓取：
- macOS：pngpaste
- Linux（X11）：xclip -selection clipboard -t image/png -o
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal


TerminalKind = Literal["iterm2", "kitty", "none"]


def detect_terminal() -> TerminalKind:
    """探测当前终端是否支持内联图片。"""
    if os.environ.get("KITTY_WINDOW_ID") or "kitty" in (os.environ.get("TERM") or ""):
        return "kitty"
    tp = os.environ.get("TERM_PROGRAM") or ""
    if tp in ("iTerm.app", "iTerm2", "WezTerm"):
        return "iterm2"
    return "none"


def render_image_bytes(data: bytes) -> str | None:
    """
    把图片字节数据转成终端可打印的字符串（含内联图片转义序列）。
    Textual App 里可以直接 print() 或 write 到底层 console 前
    暂停。TUI 场景更常见的是把这个字符串直接放进 message，让 Rich
    console 原样输出（Textual 8.x 会保留转义码）。
    不支持内联的终端返回 None。
    """
    kind = detect_terminal()
    if kind == "none":
        return None

    b64 = base64.b64encode(data).decode("ascii")
    if kind == "iterm2":
        # iTerm2 内联协议
        return f"\x1b]1337;File=inline=1;preserveAspectRatio=1:{b64}\x07"

    if kind == "kitty":
        # kitty graphics protocol —— 简单 direct mode 分块
        # 32KB 一块，太大 kitty 会分成多帧
        chunks: list[str] = []
        pos = 0
        while pos < len(b64):
            piece = b64[pos:pos + 4096]
            more = "1" if pos + 4096 < len(b64) else "0"
            if pos == 0:
                chunks.append(f"\x1b_Ga=T,f=100,m={more};{piece}\x1b\\")
            else:
                chunks.append(f"\x1b_Gm={more};{piece}\x1b\\")
            pos += 4096
        return "".join(chunks)

    return None


def render_image_file(path: Path | str) -> str | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = p.read_bytes()
    except OSError:
        return None
    return render_image_bytes(data)


# ── 剪贴板图片 ─────────────────────────────────────────

def paste_clipboard_image_bytes() -> bytes | None:
    """尝试从系统剪贴板拿图片字节；失败返回 None。"""
    if sys.platform == "darwin":
        if not shutil.which("pngpaste"):
            return None
        try:
            r = subprocess.run(
                ["pngpaste", "-"],
                capture_output=True, timeout=3,
            )
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except Exception:
            pass
        return None

    if sys.platform.startswith("linux"):
        # 先试 wl-clipboard（Wayland），再 xclip（X11）
        for cmd in [
            ["wl-paste", "--type", "image/png"],
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
        ]:
            if not shutil.which(cmd[0]):
                continue
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=3)
                if r.returncode == 0 and r.stdout:
                    return r.stdout
            except Exception:
                continue
        return None

    return None


def save_temp_image(data: bytes, suffix: str = ".png") -> Path:
    """把剪贴板拿到的图片字节写到 tmp 文件，供 backend 上传。"""
    import tempfile
    fd, name = tempfile.mkstemp(prefix="mengdie-paste-", suffix=suffix)
    os.close(fd)
    p = Path(name)
    p.write_bytes(data)
    return p
