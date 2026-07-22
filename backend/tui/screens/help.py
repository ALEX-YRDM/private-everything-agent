"""HelpModal：按 ? 弹出的快捷键帮助。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


HELP_TEXT = """[b cyan]梦蝶 TUI 快捷键[/b cyan]

[b]全局[/b]
  [yellow]?[/yellow]           显示本帮助
  [yellow]Ctrl-N[/yellow]      新建会话
  [yellow]Ctrl-C[/yellow]      中断当前生成 / 空闲时退出
  [yellow]Ctrl-Q[/yellow]      退出
  [yellow]F2[/yellow]          聚焦到输入框
  [yellow]Escape[/yellow]      退出输入模式 / 关闭弹窗

[b]视图切换（右侧 pane）[/b]
  [yellow]F3[/yellow]          文件树
  [yellow]F4[/yellow]          Todos
  [yellow]F5[/yellow]          Skills
  [yellow]F6[/yellow]          隐藏右侧 pane

[b]Plan Mode[/b]
  [yellow]Ctrl-P[/yellow]      切换 Plan Mode（进入后破坏性工具会被自动拒绝）

[b]会话列表（左侧）[/b]
  [yellow]j / k[/yellow]       上下移动
  [yellow]Enter[/yellow]       打开会话
  [yellow]d[/yellow]           删除当前会话
  [yellow]r[/yellow]           重命名当前会话

[b]输入框[/b]
  [yellow]Enter[/yellow]       发送消息
  [yellow]Shift-Enter[/yellow] 换行
  [yellow]Alt-Enter[/yellow]   换行

[b]文件树[/b]
  [yellow]Enter[/yellow]       预览文件（或展开目录）
  [yellow]Space[/yellow]       展开 / 收起目录

[b]破坏性工具确认（内联卡片）[/b]
  卡片会自动获得焦点，直接按键即可决定：
  [yellow]a[/yellow] 允许 · [yellow]d[/yellow] 拒绝 · [yellow]p[/yellow] 信任此目录 · [yellow]c[/yellow] 信任此命令
  [yellow]Enter[/yellow]=允许 · [yellow]Esc[/yellow]=拒绝

[b]输入区特殊指令[/b]
  [yellow]/rename 新标题[/yellow]   重命名当前会话
  [yellow]/delete[/yellow]           删除当前会话（要 /delete confirm 二次确认）
  [yellow]/allow <id>[/yellow]      命令行方式允许某个待确认工具
  [yellow]/deny  <id>[/yellow]      命令行方式拒绝某个待确认工具

[dim]按任意键或 Esc 关闭本窗口[/dim]
"""


class HelpModal(ModalScreen):
    """快捷键帮助弹窗。"""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    HelpModal > VerticalScroll {
        width: 80%;
        max-width: 100;
        height: 80%;
        background: $panel;
        border: heavy $accent;
        padding: 1 2;
    }
    HelpModal Static {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "关闭", show=False),
        Binding("q", "dismiss", "关闭", show=False),
        Binding("question_mark", "dismiss", "关闭", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(HELP_TEXT)

    def action_dismiss(self) -> None:
        self.app.pop_screen()
