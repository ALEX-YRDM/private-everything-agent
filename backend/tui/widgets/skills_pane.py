"""SkillsPane：显示所有可用 skills（builtin + user），按 tier 分组。

- ListView 承载条目，Enter 弹 SkillDetailModal 看完整 SKILL.md
- 依赖缺失显式标 [缺 bin:xxx]
"""
from __future__ import annotations

from typing import Any

from textual.message import Message
from textual.widgets import ListItem, ListView, Static


class SkillPreviewRequested(Message):
    def __init__(self, name: str):
        super().__init__()
        self.name = name


class _SkillItem(ListItem):
    def __init__(self, skill: dict[str, Any]):
        self.skill_name = skill.get("name") or "?"
        self.tier = skill.get("tier") or "builtin"
        available = skill.get("available", True)
        missing = skill.get("missing") or []
        desc = str(skill.get("description", "")).replace("\n", " ").strip()

        prefix_color = "green" if available else "yellow"
        tier_tag = "[dim](user)[/dim]" if self.tier == "user" else "[dim](builtin)[/dim]"
        name_safe = self.skill_name.replace("[", r"\[")
        line1 = f"[{prefix_color}]●[/{prefix_color}] [bold]{name_safe}[/bold] {tier_tag}"
        if not available and missing:
            line1 += f" [yellow dim]\\[缺 {','.join(missing)}][/yellow dim]"

        if len(desc) > 60:
            desc = desc[:60] + "…"
        desc_safe = desc.replace("[", r"\[")
        text = f"{line1}\n  [dim]{desc_safe}[/dim]"

        super().__init__(Static(text, markup=True))


class SkillsPane(ListView):
    DEFAULT_CSS = """
    SkillsPane {
        height: 1fr;
        padding: 0;
        background: transparent;
    }
    SkillsPane > ListItem {
        background: transparent;
        padding: 0 1;
    }
    SkillsPane > ListItem.--highlight {
        background: $accent 20%;
    }
    """

    def __init__(self):
        super().__init__(id="skills-pane")
        self._skills: list[dict[str, Any]] = []

    def set_skills(self, skills: list[dict[str, Any]]) -> None:
        self._skills = skills or []
        # user tier 在前
        skills_sorted = sorted(self._skills, key=lambda s: (s.get("tier") != "user",
                                                             s.get("name", "")))
        self.clear()
        for s in skills_sorted:
            self.append(_SkillItem(s))

    def on_list_view_selected(self, evt: ListView.Selected) -> None:
        item = evt.item
        if isinstance(item, _SkillItem):
            self.post_message(SkillPreviewRequested(item.skill_name))
