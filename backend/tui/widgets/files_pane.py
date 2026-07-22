"""FilesPane：右侧文件树，懒加载。

- 使用 Textual 的 Tree widget
- 只在会话有 working_dir 时有内容；否则用 workspace fallback
- 双击（或 Enter）文件 → 发一个 FilePreviewRequested 消息给父级
- 双击目录 → 展开/收起
"""
from __future__ import annotations

from pathlib import PurePosixPath

from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode


class FilePreviewRequested(Message):
    def __init__(self, path: str):
        super().__init__()
        self.path = path


class FileInsertRequested(Message):
    """双击文件 → 插入到输入框；预览走 Enter。"""

    def __init__(self, path: str):
        super().__init__()
        self.path = path


class FilesPane(Tree[dict]):
    """
    每个节点的 data:
      {'path': str, 'is_dir': bool, 'loaded': bool}
    """

    DEFAULT_CSS = """
    FilesPane {
        height: 1fr;
        background: transparent;
        padding: 0;
    }
    """

    def __init__(self):
        super().__init__("(未加载)", id="files-tree")
        self.show_root = True
        self._client = None
        self._session_id: str | None = None

    def bind_client(self, client, session_id: str) -> None:
        """由父级调用，切换会话时重置根。"""
        self._client = client
        self._session_id = session_id
        self.root.remove_children()
        self.root.data = {"path": "", "is_dir": True, "loaded": False}
        self.root.expand()  # 触发 on_tree_node_expanded

    # ── 事件 ──────────────────────────────────────

    async def on_tree_node_expanded(self, evt: Tree.NodeExpanded) -> None:
        node = evt.node
        data = node.data or {}
        if data.get("loaded") or not data.get("is_dir"):
            return
        await self._load_children(node)

    async def on_tree_node_selected(self, evt: Tree.NodeSelected) -> None:
        node = evt.node
        data = node.data or {}
        if not data:
            return
        # 目录：交给 Tree 内置的 Enter 展开逻辑（allow_expand=True 时 Tree 会自动切换）
        # 我们只处理文件的预览
        if not data.get("is_dir"):
            self.post_message(FilePreviewRequested(data["path"]))

    # ── 加载 ──────────────────────────────────────

    async def _load_children(self, node: TreeNode[dict]) -> None:
        if self._client is None or self._session_id is None:
            return
        rel_path = (node.data or {}).get("path", "")
        try:
            payload = await self._client.list_files(
                self._session_id, path=rel_path, depth=1,
            )
        except Exception as e:
            node.add_leaf(f"[dim red]加载失败: {e}[/dim red]")
            return

        entries = payload.get("entries", [])
        node.data = {**(node.data or {}), "loaded": True, "is_dir": True}

        # 更新根节点的 label 为工作目录名
        if node is self.root:
            root_path = payload.get("root", "")
            display = PurePosixPath(root_path).name or root_path
            self.root.set_label(f"📁 {display}")

        # 按目录在前、文件在后排序（后端返回字段是 type: "dir" | "file"）
        entries.sort(key=lambda e: (e.get("type") != "dir", e.get("name", "").lower()))

        for e in entries:
            name = e.get("name") or "?"
            is_dir = e.get("type") == "dir"
            # 拼子路径：rel_path/name
            child_rel = f"{rel_path}/{name}".lstrip("/") if rel_path else name

            if is_dir:
                child = node.add(f"📁 {name}", data={
                    "path": child_rel, "is_dir": True, "loaded": False,
                })
                # 允许下次展开时懒加载
                child.allow_expand = True
            else:
                node.add_leaf(f"📄 {name}", data={
                    "path": child_rel, "is_dir": False, "loaded": True,
                })
