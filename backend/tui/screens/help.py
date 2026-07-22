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
  [yellow]Ctrl-P[/yellow]      Textual 内置命令面板（主题 / 快捷键 / 最大化等）
  [yellow]Ctrl-F[/yellow]      模糊搜索会话
  [yellow]Ctrl-B[/yellow]      切换 Plan Mode
  [yellow]Ctrl-K[/yellow]      打开设置（切模型 · 支持"本会话/全局"作用范围）
  [yellow]Ctrl-W[/yellow]      设置本会话工作目录
  [yellow]Ctrl-\\[/yellow]      隐藏 / 显示左侧栏
  [yellow]Ctrl-][/yellow]      隐藏 / 显示右侧栏
  [yellow]Ctrl-C[/yellow]      中断当前生成 / 空闲时退出
  [yellow]Ctrl-Q[/yellow]      退出
  [yellow]F2[/yellow]          聚焦到输入框
  [yellow]F12[/yellow]         选择模式（关闭鼠标捕获，方便终端选中复制）
  [yellow]Escape[/yellow]      退出输入模式 / 关闭弹窗

[b]右侧 pane 切换[/b]
  [yellow]F3[/yellow]  文件  [yellow]F4[/yellow] Todos  [yellow]F5[/yellow] Skills
  [yellow]F6[/yellow]  MCP  [yellow]F7[/yellow] 信任  [yellow]F8[/yellow] 定时任务

[b]鼠标选中复制[/b]
  多数终端可以直接绕过 TUI 的鼠标捕获做选中：
    iTerm2 / Terminal.app   [yellow]Option + 拖动[/yellow]
    kitty                   [yellow]Ctrl+Shift + 拖动[/yellow]
    wezterm / Alacritty     [yellow]Shift + 拖动[/yellow]
    gnome-terminal / VSCode [yellow]Shift + 拖动[/yellow]
  或者按 [yellow]F12[/yellow] 进入 SELECT MODE 后直接选中；再按一次恢复。

[b]会话列表（左侧）[/b]
  [yellow]j / k[/yellow]       上下移动
  [yellow]Enter[/yellow]       打开会话
  [yellow]d[/yellow]           删除当前会话（配合 /delete confirm）
  [yellow]r[/yellow]           重命名当前会话（引导用 /rename 指令）

[b]输入框[/b]
  [yellow]Enter[/yellow]                       发送消息
  [yellow]Alt-Enter / Ctrl-J[/yellow]          换行（Shift-Enter 需终端配置）
  [yellow]@[/yellow]                            触发文件选择器（Space 多选）
  [yellow]/[/yellow]                            触发斜杠命令补全（↑/↓ 选择 · Tab/Enter 补全）
  拖 / 粘贴多个文件路径进输入框 → 自动加入附件区

[b]文件树[/b]
  [yellow]Enter[/yellow]       预览文件（图片走 iTerm2/kitty 内联渲染）
  [yellow]Space[/yellow]       展开 / 收起目录

[b]破坏性工具确认（内联卡片）[/b]
  卡片会自动获得焦点，直接按键即可决定：
  [yellow]a[/yellow] 允许 · [yellow]d[/yellow] 拒绝 · [yellow]p[/yellow] 信任此目录 · [yellow]c[/yellow] 信任此命令
  [yellow]Enter[/yellow]=允许 · [yellow]Esc[/yellow]=拒绝

[b]子任务卡片[/b]
  焦点到 subagent 卡片上按 [yellow]Enter[/yellow] → 弹出该子任务完整消息流

[b]附件区（InputArea 上方）[/b]
  [yellow]Backspace[/yellow] 删末尾 · [yellow]Ctrl-Delete[/yellow] 清空

[b]常用输入区指令[/b]
  [yellow]/rename 新标题[/yellow]      重命名当前会话
  [yellow]/delete[/yellow]              删除当前会话（要 /delete confirm 二次确认）
  [yellow]/paste / /paste-img[/yellow]  剪贴板图片追加到附件区（不立即发送）
  [yellow]/attach <glob>[/yellow]        批量附加本地文件（支持 ~ / 逗号分隔多 pattern）
  [yellow]/attach-clear[/yellow]         清空附件区
  [yellow]/cwd [路径][/yellow]           设置本会话工作目录（无参 → 打开选择器）
  [yellow]/model [id][/yellow]           为本会话切换模型（无参 → 打开设置）
  [yellow]/trusts[/yellow]               查看本会话已信任目录/命令
  [yellow]/copy[/yellow]                 复制最新一条 assistant 内容到剪贴板
  [yellow]/export[/yellow]               导出会话为 markdown（保存到 ~/mengdie-export-*.md）
  [yellow]/allow <id> · /deny <id>[/yellow]  命令行方式回应工具确认

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
