"""AttachmentStrip：待发附件条，位于 InputArea 上方。

- 显示待发送的图片 + 文件 chips：`[🖼 clip-1.png × ] [📄 doc.pdf × ]`
- 光标按 Delete/Backspace 从末尾移除
- Ctrl-Delete 清空
- 只在有附件时占空间
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from textual.binding import Binding
from textual.message import Message
from textual.widgets import RichLog


@dataclass
class Attachment:
    """一个附件项。图片和文件用同一个类型，image=True 走 image URI，否则走 file。"""
    label: str                       # 显示名（如 basename）
    path: str | None = None          # 本地文件绝对路径；来自剪贴板的临时文件也算
    image: bool = False              # True → 图片
    mime_type: str = ""
    data_uri: str | None = None      # 剪贴板/内存图 base64 URI
    size: int = 0


class AttachmentsChanged(Message):
    """列表变了 → 通知父级刷新状态栏 / 布局。"""

    def __init__(self, count: int) -> None:
        super().__init__()
        self.count = count


class AttachmentStrip(RichLog):
    DEFAULT_CSS = """
    AttachmentStrip {
        dock: bottom;
        height: auto;
        max-height: 4;
        margin: 0 1;
        padding: 0 1;
        background: $panel 30%;
        border: dashed $accent 40%;
        color: $foreground;
        display: none;
    }
    AttachmentStrip.-has-items {
        display: block;
    }
    """

    BINDINGS = [
        Binding("delete", "pop", show=False),
        Binding("backspace", "pop", show=False),
        Binding("ctrl+delete", "clear", show=False),
    ]

    can_focus = True

    def __init__(self) -> None:
        super().__init__(markup=True, wrap=True, highlight=False, auto_scroll=False)
        self._items: list[Attachment] = []
        self._refresh()

    # ── 对外 API ────────────────────────────────────

    @property
    def items(self) -> list[Attachment]:
        return list(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def clear_items(self) -> None:
        self._items = []
        self._refresh()
        self._notify()

    def add(self, att: Attachment) -> None:
        self._items.append(att)
        self._refresh()
        self._notify()

    def add_many(self, atts: list[Attachment]) -> None:
        if not atts:
            return
        self._items.extend(atts)
        self._refresh()
        self._notify()

    def pop_last(self) -> None:
        if self._items:
            self._items.pop()
            self._refresh()
            self._notify()

    # ── action ─────────────────────────────────────

    def action_pop(self) -> None:
        self.pop_last()

    def action_clear(self) -> None:
        self.clear_items()

    # ── 渲染 ───────────────────────────────────────

    def _refresh(self) -> None:
        self.clear()
        if not self._items:
            self.remove_class("-has-items")
            return
        self.add_class("-has-items")

        chips: list[str] = []
        for i, a in enumerate(self._items):
            icon = "🖼" if a.image else "📄"
            label = str(a.label).replace("[", r"\[")[:32]
            chips.append(f"[cyan]{icon}[/cyan] [bold]{label}[/bold]")
        line = "  ".join(chips)
        self.write(
            f"[dim]附件 ({len(self._items)})：[/dim] {line}"
            f"  [dim]Backspace 删末尾 · Ctrl-Del 清空[/dim]"
        )

    def _notify(self) -> None:
        try:
            self.post_message(AttachmentsChanged(len(self._items)))
        except Exception:
            pass


# ── 辅助 ────────────────────────────────────────────

def _guess_mime(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    return {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
        "svg": "image/svg+xml",
        "pdf": "application/pdf",
        "md": "text/markdown", "txt": "text/plain",
    }.get(ext, "application/octet-stream")


IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"}


def build_from_path(path: str) -> Attachment | None:
    """从本地路径构造 Attachment；图片走 data URI，其他文件按 base64 保留字节。

    读文件失败或纯二进制非图返回 None。
    """
    import base64

    p = Path(path).expanduser()
    if not p.is_file():
        return None
    try:
        raw = p.read_bytes()
    except Exception:
        return None

    ext = p.suffix.lower().lstrip(".")
    if ext in IMAGE_EXTS:
        mime = _guess_mime(str(p))
        uri = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        return Attachment(
            label=p.name, path=str(p), image=True, mime_type=mime,
            data_uri=uri, size=len(raw),
        )

    # 非图片：按 base64 存字节；后端 parse_file 会按 mime 走对应解析器
    mime = _guess_mime(str(p))
    return Attachment(
        label=p.name, path=str(p), image=False,
        mime_type=mime, size=len(raw),
        data_uri=base64.b64encode(raw).decode("ascii"),
    )


def build_from_clipboard() -> Attachment | None:
    """尝试从剪贴板拿一张图 → 生成内联 Attachment。"""
    import base64
    from ..imaging import paste_clipboard_image_bytes

    data = paste_clipboard_image_bytes()
    if not data:
        return None
    uri = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    return Attachment(
        label="clipboard.png", path=None, image=True,
        mime_type="image/png", data_uri=uri, size=len(data),
    )
