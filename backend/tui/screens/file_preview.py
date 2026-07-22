"""FilePreviewModal：只读预览一个文件的内容，带语法高亮。"""
from __future__ import annotations

from pathlib import PurePosixPath

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


LEXER_BY_EXT = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".jsx": "jsx",
    ".vue": "html",  # rough
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".html": "html", ".css": "css",
    ".sh": "bash", ".go": "go", ".rs": "rust",
    ".java": "java", ".c": "c", ".cpp": "cpp",
    ".sql": "sql", ".toml": "toml",
}


class FilePreviewModal(ModalScreen):
    DEFAULT_CSS = """
    FilePreviewModal {
        align: center middle;
    }
    FilePreviewModal > VerticalScroll {
        width: 90%;
        max-width: 140;
        height: 88%;
        background: $panel;
        border: heavy $accent;
        padding: 0 1;
    }
    #preview-title {
        color: $accent;
        text-style: bold;
        padding: 1 1 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("q", "close", show=False),
    ]

    def __init__(self, path: str, content: str, truncated: bool = False):
        super().__init__()
        self.path = path
        self.content = content
        self.truncated = truncated

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(f"📄 {self.path}"
                         + ("  [yellow](已截断)[/yellow]" if self.truncated else ""),
                         id="preview-title")
            ext = "." + self.path.rsplit(".", 1)[-1].lower() if "." in self.path else ""
            lexer = LEXER_BY_EXT.get(ext)
            if lexer:
                yield Static(Syntax(self.content, lexer, theme="ansi_dark",
                                    background_color="default", word_wrap=True,
                                    line_numbers=True))
            else:
                yield Static(Text(self.content))

    def action_close(self) -> None:
        self.app.pop_screen()
