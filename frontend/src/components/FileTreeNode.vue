<script lang="ts">
import { defineComponent, h } from 'vue'
import { NSpin } from 'naive-ui'
import type { FileNode } from '../api/http'

/** 递归渲染文件树节点。用 h() 手写以支持深度递归。 */
export default defineComponent({
  name: 'FileTreeNode',
  props: {
    node: { type: Object as () => FileNode, required: true },
    depth: { type: Number, required: true },
    expanded: { type: Object as () => Set<string>, required: true },
    loadingPaths: { type: Object as () => Set<string>, required: true },
  },
  emits: {
    toggle: (_node: FileNode) => true,
  },
  setup(props, { emit }) {
    // 递归引用自身组件类型
    const self = { name: 'FileTreeNode' } as any

    return () => {
      const isDir = props.node.type === 'dir'
      const isOpen = props.expanded.has(props.node.path)
      const isLoading = props.loadingPaths.has(props.node.path)
      const indent = props.depth * 12

      const row = h(
        'div',
        {
          class: ['tree-row', { dir: isDir, file: !isDir }],
          style: { paddingLeft: `${indent + 8}px` },
          onClick: () => emit('toggle', props.node),
          title: isDir ? '点击展开/收起' : '点击插入路径到输入框',
        },
        [
          h('span', { class: 'tree-icon' }, isDir ? (isOpen ? '▾' : '▸') : '·'),
          h('span', { class: 'tree-name' }, props.node.name),
          isLoading ? h(NSpin, { size: 'small', style: 'margin-left:auto' }) : null,
        ],
      )

      const children =
        isDir && isOpen && props.node.children
          ? props.node.children.map((child) =>
              h(self, {
                key: child.path,
                node: child,
                depth: props.depth + 1,
                expanded: props.expanded,
                loadingPaths: props.loadingPaths,
                onToggle: (n: FileNode) => emit('toggle', n),
              }),
            )
          : []

      return h('div', {}, [row, ...children])
    }
  },
})
</script>

<style>
.tree-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  cursor: pointer;
  font-size: 12px;
  color: #333;
  border-radius: 4px;
  margin: 1px 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tree-row:hover { background: #eef2f7; }
.tree-row.dir { color: #1677ff; font-weight: 500; }
.tree-icon { width: 10px; color: #999; flex-shrink: 0; }
.tree-name { overflow: hidden; text-overflow: ellipsis; }
</style>
