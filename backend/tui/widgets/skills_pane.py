"""SkillsPane：显示所有可用 skills（builtin + user），按 tier 分组。"""
from __future__ import annotations

from typing import Any

from textual.widgets import RichLog


class SkillsPane(RichLog):
    DEFAULT_CSS = """
    SkillsPane {
        height: 1fr;
        padding: 0 1;
        background: transparent;
    }
    """

    def __init__(self):
        super().__init__(id="skills-pane", markup=True, wrap=True, highlight=False)
        self._skills: list[dict[str, Any]] = []

    def on_mount(self) -> None:
        self._render()

    def set_skills(self, skills: list[dict[str, Any]]) -> None:
        self._skills = skills or []
        self._render()

    def _render(self) -> None:
        self.clear()
        if not self._skills:
            self.write("[dim]【未加载】[/dim]")
            return

        user_skills = [s for s in self._skills if s.get("tier") == "user"]
        builtin_skills = [s for s in self._skills if s.get("tier") != "user"]

        if user_skills:
            self.write(f"[bold cyan]用户技能 ({len(user_skills)})[/bold cyan]")
            for s in user_skills:
                self._write_one(s)
            self.write("")
        if builtin_skills:
            self.write(f"[bold cyan]内置技能 ({len(builtin_skills)})[/bold cyan]")
            for s in builtin_skills:
                self._write_one(s)

    def _write_one(self, s: dict[str, Any]) -> None:
        name = str(s.get("name", "?")).replace("[", r"\[")
        desc = str(s.get("description", "")).replace("[", r"\[")
        available = s.get("available", True)
        missing = s.get("missing") or []
        prefix_color = "green" if available else "yellow"

        head = f"[{prefix_color}]●[/{prefix_color}] [bold]{name}[/bold]"
        if not available and missing:
            miss_str = ",".join(missing)
            head += f" [yellow dim]\\[缺 {miss_str}][/yellow dim]"
        one_line = desc.replace("\n", " ").strip()
        if len(one_line) > 80:
            one_line = one_line[:80] + "…"
        self.write(f"  {head}")
        self.write(f"    [dim]{one_line}[/dim]")
