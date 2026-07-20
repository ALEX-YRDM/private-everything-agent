<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NScrollbar, NEmpty, NSpin, NButton, NTooltip, useMessage } from 'naive-ui'
import { api, type FileNode } from '../api/http'

const props = defineProps<{
  sessionId: string | null
  workingDir: string | null
}>()
const emit = defineEmits<{
  'insert-path': [path: string]
}>()

const message = useMessage()

// ── 数据模型 ───────────────────────────────────────────────────────────────
// 用 path → FileNode[] 的映射存所有已加载的目录内容。
// 根目录的 children 存在 childrenByPath[""] 下，保持一致。
const root = ref('')
const childrenByPath = ref<Record<string, FileNode[]>>({})
const expanded = ref<Record<string, boolean>>({})
const loadingPath = ref<string | null>(null)
const rootLoading = ref(false)

// ── 数据加载 ───────────────────────────────────────────────────────────────
async function loadRoot() {
  if (!props.sessionId || !props.workingDir) {
    root.value = ''
    childrenByPath.value = {}
    return
  }
  rootLoading.value = true
  try {
    const data = await api.sessions.listFiles(props.sessionId, '', 1)
    root.value = data.root
    childrenByPath.value = { '': data.entries }
    expanded.value = {}
  } catch (e: any) {
    message.error(`加载文件树失败: ${e?.message || e}`)
  } finally {
    rootLoading.value = false
  }
}

async function loadChildren(path: string) {
  if (!props.sessionId) return
  loadingPath.value = path
  try {
    const data = await api.sessions.listFiles(props.sessionId, path, 1)
    childrenByPath.value = { ...childrenByPath.value, [path]: data.entries }
  } catch (e: any) {
    message.warning(`加载 ${path} 失败: ${e?.message || e}`)
  } finally {
    if (loadingPath.value === path) loadingPath.value = null
  }
}

// ── 交互 ──────────────────────────────────────────────────────────────────
async function onRowClick(node: FileNode) {
  if (node.type === 'file') {
    emit('insert-path', node.path)
    return
  }
  if (expanded.value[node.path]) {
    expanded.value = { ...expanded.value, [node.path]: false }
  } else {
    expanded.value = { ...expanded.value, [node.path]: true }
    if (!childrenByPath.value[node.path]) {
      await loadChildren(node.path)
    }
  }
}

// ── 扁平化：把整棵已展开的树折叠成 v-for 可渲染的行数组 ─────────────────────
interface Row {
  node: FileNode
  depth: number
  isOpen: boolean
  isLoading: boolean
}

const rows = computed<Row[]>(() => {
  const result: Row[] = []

  function visit(nodes: FileNode[] | undefined, depth: number) {
    if (!nodes) return
    for (const n of nodes) {
      const isOpen = !!expanded.value[n.path]
      const isLoading = loadingPath.value === n.path
      result.push({ node: n, depth, isOpen, isLoading })
      if (n.type === 'dir' && isOpen) {
        // 子节点可能来自懒加载缓存，或初始返回时后端已带的 children
        const children = childrenByPath.value[n.path] ?? n.children
        visit(children, depth + 1)
      }
    }
  }

  visit(childrenByPath.value[''], 0)
  return result
})

watch(
  () => [props.sessionId, props.workingDir],
  () => loadRoot(),
  { immediate: true },
)

const displayRoot = computed(() => {
  if (!root.value) return ''
  const parts = root.value.split('/')
  return parts[parts.length - 1] || root.value
})

// ── 工具：文件图标（按扩展名） ─────────────────────────────────────────────
function fileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, string> = {
    md: '📝', markdown: '📝',
    py: '🐍',
    js: '📜', mjs: '📜', cjs: '📜',
    ts: '📘', tsx: '📘',
    jsx: '⚛️',
    vue: '💚',
    json: '📦',
    yml: '⚙️', yaml: '⚙️', toml: '⚙️',
    lock: '🔒',
    css: '🎨', scss: '🎨',
    html: '🌐',
    sh: '💻', bash: '💻', zsh: '💻',
    png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', svg: '🖼️',
    sql: '🗃️', db: '🗃️', sqlite: '🗃️',
    txt: '📄',
    gitignore: '🙈',
    env: '🔐',
  }
  return map[ext] || '📄'
}
</script>

<template>
  <aside class="file-tree-panel">
    <header class="ft-header">
      <div class="ft-title-row">
        <span class="ft-title">
          <span class="ft-emoji">📁</span>
          {{ displayRoot || '文件树' }}
        </span>
        <NTooltip>
          <template #trigger>
            <NButton
              size="tiny"
              quaternary
              circle
              :loading="rootLoading"
              @click="loadRoot"
            >⟳</NButton>
          </template>
          刷新
        </NTooltip>
      </div>
      <div v-if="root" class="ft-path" :title="root">{{ root }}</div>
    </header>

    <NScrollbar class="ft-scroll">
      <div v-if="!workingDir" class="ft-empty">
        <NEmpty description="此会话未设置工作目录" size="small" />
      </div>
      <div v-else-if="rootLoading && rows.length === 0" class="ft-empty">
        <NSpin size="small" />
      </div>
      <div v-else-if="rows.length === 0" class="ft-empty">
        <NEmpty description="空目录" size="small" />
      </div>
      <div v-else class="ft-list">
        <div
          v-for="row in rows"
          :key="row.node.path"
          class="ft-row"
          :class="{
            'is-dir': row.node.type === 'dir',
            'is-file': row.node.type === 'file',
            'is-open': row.isOpen,
          }"
          :style="{ paddingLeft: `${8 + row.depth * 14}px` }"
          :title="row.node.type === 'dir' ? '展开/收起' : '点击插入路径到输入框'"
          @click="onRowClick(row.node)"
        >
          <span v-if="row.node.type === 'dir'" class="ft-caret">
            {{ row.isOpen ? '▾' : '▸' }}
          </span>
          <span v-else class="ft-caret-spacer"></span>

          <span class="ft-icon">
            {{ row.node.type === 'dir'
              ? (row.isOpen ? '📂' : '📁')
              : fileIcon(row.node.name) }}
          </span>

          <span class="ft-name">{{ row.node.name }}</span>

          <NSpin v-if="row.isLoading" size="small" class="ft-loading" />
        </div>
      </div>
    </NScrollbar>
  </aside>
</template>

<style scoped>
.file-tree-panel {
  width: 280px;
  min-width: 240px;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
}

.ft-header {
  padding: 12px 14px 10px;
  border-bottom: 1px solid #ececec;
  background: white;
}

.ft-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ft-title {
  font-weight: 600;
  font-size: 13px;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.ft-emoji { flex-shrink: 0; }

.ft-path {
  margin-top: 4px;
  font-size: 11px;
  color: #9ca3af;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ft-scroll { flex: 1; }

.ft-empty {
  padding: 40px 12px;
  text-align: center;
}

.ft-list {
  padding: 4px 0;
}

.ft-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px 3px 0;
  cursor: pointer;
  font-size: 12.5px;
  line-height: 20px;
  color: #374151;
  white-space: nowrap;
  overflow: hidden;
  user-select: none;
  transition: background 0.1s;
  min-height: 24px;
}
.ft-row:hover { background: #eef2f7; }
.ft-row.is-open { background: rgba(22, 119, 255, 0.04); }
.ft-row.is-dir { color: #1e40af; font-weight: 500; }
.ft-row.is-file { color: #4b5563; }

.ft-caret {
  width: 10px;
  color: #94a3b8;
  font-size: 9px;
  flex-shrink: 0;
  text-align: center;
}
.ft-caret-spacer { width: 10px; flex-shrink: 0; }

.ft-icon {
  font-size: 13px;
  flex-shrink: 0;
  width: 16px;
  text-align: center;
}

.ft-name {
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.ft-loading {
  margin-left: auto;
  flex-shrink: 0;
}
</style>
