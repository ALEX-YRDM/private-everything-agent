<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { NScrollbar, NEmpty, NSpin, NButton, NTooltip, NDropdown, useMessage } from 'naive-ui'
import { api, type FileNode } from '../api/http'
import { useLayoutStore, COLLAPSED_WIDTH } from '../stores/layout'
import { useChatStore } from '../stores/chat'
import { useCodeViewerStore } from '../stores/codeViewer'
import ResizeHandle from './ResizeHandle.vue'

const props = defineProps<{
  sessionId: string | null
  workingDir: string | null
}>()
const emit = defineEmits<{
  'insert-path': [path: string]
}>()

const message = useMessage()
const layout = useLayoutStore()
const chat = useChatStore()
const codeViewer = useCodeViewerStore()

// Git 状态：path → 状态字符（M / A / ? / D / R）
const gitFiles = ref<Record<string, string>>({})
const gitBranch = ref<string | null>(null)
const gitIsRepo = ref(false)

async function loadGitStatus() {
  if (!props.sessionId || !props.workingDir) {
    gitFiles.value = {}
    gitBranch.value = null
    gitIsRepo.value = false
    return
  }
  try {
    const data = await api.sessions.gitStatus(props.sessionId)
    gitIsRepo.value = data.is_git
    gitBranch.value = data.branch
    gitFiles.value = data.files
  } catch {
    // 静默失败：非 git 目录 / 权限问题
    gitFiles.value = {}
    gitBranch.value = null
    gitIsRepo.value = false
  }
}

/** 目录 badge：若目录下有任何变更文件就标记 */
function dirBadge(dirPath: string): string | null {
  const prefix = dirPath.endsWith('/') ? dirPath : dirPath + '/'
  for (const p of Object.keys(gitFiles.value)) {
    if (p === dirPath || p.startsWith(prefix)) return '●'
  }
  return null
}

// 拖拽调宽
let resizeStartWidth = 0
function onResizeStart() { resizeStartWidth = layout.rightWidth }
function onResize(delta: number) {
  // handle 在左侧，拖向左 → deltaX < 0 → 宽度增加；反之亦然
  layout.setRightWidth(resizeStartWidth - delta)
}

const width = computed(() =>
  layout.rightCollapsed ? COLLAPSED_WIDTH : layout.rightWidth,
)

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

async function refreshAll() {
  await Promise.all([loadRoot(), loadGitStatus()])
}

/** 各状态计数（M / A / ? / D） */
const gitCounts = computed(() => {
  const counts: Record<string, number> = { M: 0, A: 0, '?': 0, D: 0 }
  for (const v of Object.values(gitFiles.value)) {
    if (counts[v] !== undefined) counts[v]++
    else counts[v] = 1
  }
  return counts
})

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
// 单击：文件 → 无操作（避免误触把路径塞进输入框）；目录 → 展开/收起
// 双击：文件 → 用浏览器预览
// 右键：菜单（附加/插入路径/预览）
async function onRowClick(node: FileNode) {
  if (node.type === 'file') return
  if (expanded.value[node.path]) {
    expanded.value = { ...expanded.value, [node.path]: false }
  } else {
    expanded.value = { ...expanded.value, [node.path]: true }
    if (!childrenByPath.value[node.path]) {
      await loadChildren(node.path)
    }
  }
}

function onRowDblClick(node: FileNode) {
  if (node.type !== 'file' || !props.sessionId) return
  codeViewer.openFile(props.sessionId, node.path)
}

// ── 右键菜单 ──────────────────────────────────────────────────────────────
const ctxMenuShow = ref(false)
const ctxMenuX = ref(0)
const ctxMenuY = ref(0)
const ctxMenuNode = ref<FileNode | null>(null)

const ctxMenuOptions = computed(() => {
  const n = ctxMenuNode.value
  if (!n) return []
  if (n.type === 'file') {
    return [
      { label: '用浏览器打开（预览）', key: 'preview', icon: () => '📖' },
      { label: '附加到下条消息（@）', key: 'attach', icon: () => '📎' },
      { label: '插入路径到输入框', key: 'insert', icon: () => '📝' },
    ]
  }
  return [
    { label: '刷新此目录', key: 'refresh', icon: () => '⟳' },
  ]
})

function onRowContextMenu(e: MouseEvent, node: FileNode) {
  e.preventDefault()
  ctxMenuNode.value = node
  ctxMenuX.value = e.clientX
  ctxMenuY.value = e.clientY
  ctxMenuShow.value = false
  nextTick(() => { ctxMenuShow.value = true })
}

function onCtxMenuSelect(key: string) {
  const n = ctxMenuNode.value
  ctxMenuShow.value = false
  if (!n) return
  if (key === 'attach' && n.type === 'file') {
    const added = chat.addAttachment(n.path)
    if (added) message.success(`已附加 ${n.path}`)
    else message.info(`${n.path} 已在附加列表中`)
  } else if (key === 'insert') {
    emit('insert-path', n.path)
  } else if (key === 'preview' && n.type === 'file' && props.sessionId) {
    codeViewer.openFile(props.sessionId, n.path)
  } else if (key === 'refresh' && n.type === 'dir') {
    loadChildren(n.path)
  }
}
function onCtxMenuClickOutside() {
  ctxMenuShow.value = false
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
  () => {
    loadRoot()
    loadGitStatus()
  },
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
  <aside
    class="file-tree-panel"
    :class="{ collapsed: layout.rightCollapsed }"
    :style="{ width: width + 'px' }"
  >
    <!-- 左侧拖拽 handle -->
    <ResizeHandle
      v-if="!layout.rightCollapsed"
      side="right"
      @resize-start="onResizeStart"
      @resize="onResize"
    />

    <!-- 折叠态：一条竖条 -->
    <div v-if="layout.rightCollapsed" class="collapsed-bar" @click="layout.toggleRight()" title="展开文件树">
      <span class="collapsed-hint">‹</span>
      <span class="collapsed-icon">📁</span>
    </div>

    <template v-else>
      <header class="ft-header">
        <div class="ft-title-row">
          <span class="ft-title">
            <span class="ft-emoji">📁</span>
            {{ displayRoot || '文件树' }}
          </span>
          <div class="ft-header-btns">
            <NTooltip>
              <template #trigger>
                <NButton
                  size="tiny"
                  quaternary
                  circle
                  :loading="rootLoading"
                  @click="refreshAll"
                >⟳</NButton>
              </template>
              刷新（含 Git 状态）
            </NTooltip>
            <NTooltip>
              <template #trigger>
                <button class="collapse-btn" @click="layout.toggleRight()">›</button>
              </template>
              折叠
            </NTooltip>
          </div>
        </div>
        <div v-if="root" class="ft-path" :title="root">{{ root }}</div>
        <div v-if="gitIsRepo" class="ft-git-line">
          <span class="ft-git-branch" :title="gitBranch || ''">
            <span class="ft-git-icon">⎇</span>{{ gitBranch || 'HEAD' }}
          </span>
          <span v-if="(gitCounts.M ?? 0) > 0" class="ft-git-stat stat-M">M {{ gitCounts.M }}</span>
          <span v-if="(gitCounts.A ?? 0) > 0" class="ft-git-stat stat-A">A {{ gitCounts.A }}</span>
          <span v-if="(gitCounts['?'] ?? 0) > 0" class="ft-git-stat stat-Q">? {{ gitCounts['?'] }}</span>
          <span v-if="(gitCounts.D ?? 0) > 0" class="ft-git-stat stat-D">D {{ gitCounts.D }}</span>
        </div>
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
              'is-attached': row.node.type === 'file' && chat.pendingAttachments.includes(row.node.path),
            }"
            :style="{ paddingLeft: `${8 + row.depth * 14}px` }"
            :title="row.node.type === 'dir' ? '点击展开/收起，右键刷新' : '双击=预览 · 右键=附加 / 插入路径 / 预览'"
            @click="onRowClick(row.node)"
            @dblclick="onRowDblClick(row.node)"
            @contextmenu="onRowContextMenu($event, row.node)"
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

            <span
              v-if="row.node.type === 'file' && gitFiles[row.node.path]"
              class="ft-git-badge"
              :class="`badge-${gitFiles[row.node.path] === '?' ? 'Q' : gitFiles[row.node.path]}`"
              :title="`Git 状态: ${gitFiles[row.node.path]}`"
            >{{ gitFiles[row.node.path] }}</span>
            <span
              v-else-if="row.node.type === 'dir' && dirBadge(row.node.path)"
              class="ft-git-badge badge-dir"
              title="此目录下有未提交变更"
            >●</span>

            <NSpin v-if="row.isLoading" size="small" class="ft-loading" />
            <span
              v-if="row.node.type === 'file' && chat.pendingAttachments.includes(row.node.path)"
              class="ft-attached-marker"
              title="已附加到下条消息"
            >📎</span>
          </div>
        </div>
      </NScrollbar>
    </template>

    <!-- 右键菜单 -->
    <NDropdown
      trigger="manual"
      placement="bottom-start"
      :show="ctxMenuShow"
      :options="ctxMenuOptions"
      :x="ctxMenuX"
      :y="ctxMenuY"
      @select="onCtxMenuSelect"
      @clickoutside="onCtxMenuClickOutside"
    />
  </aside>
</template>

<style scoped>
.file-tree-panel {
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  position: relative;
  flex-shrink: 0;
}
.file-tree-panel.collapsed { cursor: pointer; }

.collapsed-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  gap: 8px;
  height: 100%;
  transition: background 0.15s;
}
.collapsed-bar:hover { background: #f0f0f0; }
.collapsed-icon { font-size: 16px; }
.collapsed-hint {
  color: #9ca3af;
  font-size: 14px;
  font-weight: 700;
}

.ft-header {
  padding: 12px 14px 10px;
  border-bottom: 1px solid #ececec;
  background: white;
}

.ft-header-btns {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.collapse-btn {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #6b7280;
  line-height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.collapse-btn:hover { background: #e5e7eb; color: #1677ff; }

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

.ft-attached-marker {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 11px;
  opacity: 0.85;
}

/* Git 状态徽章 */
.ft-git-badge {
  margin-left: auto;
  flex-shrink: 0;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 10px;
  font-weight: 600;
  padding: 0 4px;
  border-radius: 3px;
  min-width: 14px;
  text-align: center;
  line-height: 14px;
}
.badge-M { color: #b45309; background: #fef3c7; }
.badge-A { color: #15803d; background: #dcfce7; }
.badge-Q { color: #6b7280; background: #f3f4f6; }
.badge-D { color: #b91c1c; background: #fee2e2; }
.badge-R { color: #1e40af; background: #dbeafe; }
.badge-dir { color: #6b7280; background: transparent; font-size: 8px; }

/* Git 状态头部行 */
.ft-git-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 10.5px;
  flex-wrap: wrap;
}
.ft-git-branch {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 6px;
  background: #eef4ff;
  border: 1px solid #bfd4ff;
  color: #1e40af;
  border-radius: 4px;
  font-family: 'SF Mono', 'Monaco', monospace;
}
.ft-git-icon { font-size: 11px; }
.ft-git-stat {
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-weight: 600;
}
.ft-git-stat.stat-M { color: #b45309; background: #fef3c7; }
.ft-git-stat.stat-A { color: #15803d; background: #dcfce7; }
.ft-git-stat.stat-Q { color: #6b7280; background: #f3f4f6; }
.ft-git-stat.stat-D { color: #b91c1c; background: #fee2e2; }

.ft-row.is-attached {
  background: rgba(22, 119, 255, 0.08);
}
.ft-row.is-attached.is-file { color: #1677ff; font-weight: 500; }
</style>
