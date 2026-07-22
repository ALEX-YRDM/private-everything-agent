"""SkillDetailModal：Skill 完整信息 + SKILL.md 内容预览。"""
from __future__ import annotations

from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class SkillDetailModal(ModalScreen):
    DEFAULT_CSS = """
    SkillDetailModal {
        align: center middle;
    }
    SkillDetailModal > VerticalScroll {
        width: 85%;
        max-width: 120;
        height: 85%;
        background: $panel;
        border: heavy $accent;
        padding: 1 2;
    }
    #skill-detail-header {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    #skill-detail-meta {
        color: $text-muted;
        margin-bottom: 1;
    }
    #skill-detail-body {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("q", "close", show=False),
    ]

    def __init__(self, skill: dict):
        super().__init__()
        self.skill = skill

    def compose(self) -> ComposeResult:
        s = self.skill
        name = s.get("name", "?")
        tier = s.get("tier", "?")
        desc = s.get("description", "")
        when = s.get("when", "")
        path = s.get("path", "")
        missing = s.get("missing") or []
        content = s.get("content", "")

        with VerticalScroll():
            yield Static(f"📘 {name}  [dim]({tier})[/dim]", id="skill-detail-header",
                         markup=True)

            meta_lines: list[str] = [f"[dim]描述：[/dim]{desc}"]
            if when:
                meta_lines.append(f"[dim]触发：[/dim]{when}")
            if missing:
                meta_lines.append(f"[yellow dim]缺失：{','.join(missing)}[/yellow dim]")
            if path:
                meta_lines.append(f"[dim]路径：{path}[/dim]")
            yield Static("\n".join(meta_lines), id="skill-detail-meta", markup=True)

            # SKILL.md 正文
            if content:
                try:
                    yield Static(Markdown(content, code_theme="monokai"),
                                 id="skill-detail-body")
                except Exception:
                    yield Static(content, id="skill-detail-body")

    def action_close(self) -> None:
        self.app.pop_screen()
