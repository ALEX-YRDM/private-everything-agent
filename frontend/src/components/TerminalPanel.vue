<script setup lang="ts">
/**
 * 终端抽屉：从右侧滑出，支持多 tab。
 *
 * - 每个 tab 是一个独立的 TerminalTabInstance（独立 pty + ws + xterm 实例）
 * - 切 tab 只是 v-show 切换，不销毁后台 tab 的 shell
 * - 抽屉宽度可拖调；持久化在 layout store
 */
import { ref, watch, computed, nextTick, useTemplateRef } from 'vue'
import { NButton, NTooltip } from 'naive-ui'
import ResizeHandle from './ResizeHandle.vue'
import TerminalTabInstance from './TerminalTabInstance.vue'
import { useChatStore } from '../stores/chat'
import { useLayoutStore } from '../stores/layout'
import { useTerminalStore } from '../stores/terminal'

const chat = useChatStore()
const layout = useLayoutStore()
const store = useTerminalStore()

const instances = useTemplateRef<InstanceType<typeof TerminalTabInstance>[]>('instances')

// 首次打开抽屉：如果一个 tab 都没有 → 自动开一个
watch(() => layout.terminalOpen, (v) => {
  if (v && store.tabs.length === 0 && chat.currentSessionId) {
    store.createTab()
  }
})

// 只要有会话就允许开终端；没绑定 working_dir 时后端自动 fallback 到默认 workspace
const canOpen = computed(() => !!chat.currentSessionId)

function newTab() {
  if (!canOpen.value) return
  store.createTab()
  nextTick(() => {
    // 让新 tab 拿到焦点
    const inst = instances.value?.[instances.value.length - 1]
    inst?.$el?.querySelector?.('.xterm-helper-textarea')?.focus?.()
  })
}

function reconnectActive() {
  const idx = store.tabs.findIndex((t) => t.id === store.activeId)
  if (idx < 0) return
  instances.value?.[idx]?.reconnect()
}
function sendCtrlCActive() {
  const idx = store.tabs.findIndex((t) => t.id === store.activeId)
  if (idx < 0) return
  instances.value?.[idx]?.sendCtrlC()
}
function clearScreenActive() {
  const idx = store.tabs.findIndex((t) => t.id === store.activeId)
  if (idx < 0) return
  instances.value?.[idx]?.clearScreen()
}

// 拖拽调宽
let startW = 0
function onResizeStart() { startW = layout.terminalWidth }
function onResize(delta: number) {
  // handle 在左侧，向左拖 → 加宽
  layout.setTerminalWidth(startW - delta)
}

// tab 重命名（双击 tab 标题）
const editingId = ref<string | null>(null)
const editingTitle = ref('')
function startRename(id: string, title: string) {
  editingId.value = id
  editingTitle.value = title
}
function commitRename() {
  if (editingId.value) {
    store.renameTab(editingId.value, editingTitle.value.trim())
  }
  editingId.value = null
}
function cancelRename() { editingId.value = null }
</script>

<template>
  <aside
    v-if="layout.terminalOpen"
    class="term-drawer"
    :style="{ width: layout.terminalWidth + 'px' }"
  >
    <ResizeHandle side="right" @resize-start="onResizeStart" @resize="onResize" />

    <div class="td-header">
      <span class="td-title">🖥 终端</span>

      <div class="td-tabs">
        <div
          v-for="tab in store.tabs"
          :key="tab.id"
          class="td-tab"
          :class="[{ active: tab.id === store.activeId }, `s-${tab.status}`]"
          :title="`${tab.title}${tab.cwd ? ' · ' + tab.cwd : ''}`"
          @click="store.switchTab(tab.id)"
          @dblclick="startRename(tab.id, tab.title)"
        >
          <span class="td-tab-dot" />
          <template v-if="editingId === tab.id">
            <input
              class="td-tab-input"
              v-model="editingTitle"
              @blur="commitRename"
              @keydown.enter.stop="commitRename"
              @keydown.esc.stop="cancelRename"
              @click.stop
              autofocus
            />
          </template>
          <template v-else>
            <span class="td-tab-name">{{ tab.title }}</span>
          </template>
          <button class="td-tab-x" @click.stop="store.closeTab(tab.id)" title="关闭">×</button>
        </div>
        <NTooltip>
          <template #trigger>
            <button class="td-newtab" @click="newTab" :disabled="!canOpen">+</button>
          </template>
          {{ canOpen ? '新建终端 tab' : '请先选择一个会话' }}
        </NTooltip>
      </div>

      <span class="td-spacer" />

      <NTooltip v-if="store.activeTab">
        <template #trigger>
          <NButton size="tiny" quaternary
                   :disabled="store.activeTab.status !== 'connected'"
                   @click="sendCtrlCActive">Ctrl+C</NButton>
        </template>
        向 shell 发送 SIGINT
      </NTooltip>
      <NTooltip v-if="store.activeTab">
        <template #trigger>
          <NButton size="tiny" quaternary @click="clearScreenActive">清屏</NButton>
        </template>
        清空终端显示（Ctrl+L 也可）
      </NTooltip>
      <NTooltip v-if="store.activeTab">
        <template #trigger>
          <NButton size="tiny" quaternary @click="reconnectActive">⟳</NButton>
        </template>
        重连（会关闭当前 shell）
      </NTooltip>
      <NTooltip>
        <template #trigger>
          <NButton size="tiny" quaternary @click="layout.toggleTerminal()">×</NButton>
        </template>
        关闭终端抽屉（tab 会保留，下次打开还在）
      </NTooltip>
    </div>

    <div v-if="!canOpen" class="td-empty">
      <p>请先在左侧选择或新建一个会话。</p>
    </div>

    <div v-else-if="!store.tabs.length" class="td-empty">
      <p>还没有终端 tab</p>
      <NButton type="primary" size="small" @click="newTab">新建一个</NButton>
    </div>

    <div v-else class="td-body">
      <TerminalTabInstance
        v-for="tab in store.tabs"
        :key="tab.id"
        ref="instances"
        :tab="tab"
        :active="tab.id === store.activeId"
      />
    </div>
  </aside>
</template>

<style scoped>
.term-drawer {
  position: relative;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
  border-left: 1px solid #2a2a2a;
  flex-shrink: 0;
  min-width: 320px;
}

.td-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 12px;
  background: #2a2a2a;
  border-bottom: 1px solid #3a3a3a;
  color: #d4d4d4;
  font-size: 12px;
  flex-shrink: 0;
  overflow: hidden;
}

.td-title {
  font-weight: 600;
  flex-shrink: 0;
  padding-right: 4px;
  border-right: 1px solid #3a3a3a;
  margin-right: 2px;
}

.td-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
}

.td-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 4px 3px 8px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  color: #9ca3af;
  font-size: 11.5px;
  white-space: nowrap;
  transition: background 0.1s;
  flex-shrink: 0;
  max-width: 180px;
}
.td-tab:hover { background: rgba(255, 255, 255, 0.06); color: #d4d4d4; }
.td-tab.active {
  background: #1e1e1e;
  color: #79c0ff;
  border-color: #3a3a3a;
}

.td-tab-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #6b7280;
  flex-shrink: 0;
}
.td-tab.s-connected .td-tab-dot { background: #56d364; }
.td-tab.s-connecting .td-tab-dot { background: #f0d370; animation: pulse 1.2s infinite; }
.td-tab.s-closed .td-tab-dot { background: #f78166; }

.td-tab-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.td-tab-input {
  background: #1e1e1e;
  color: #d4d4d4;
  border: 1px solid #3a3a3a;
  border-radius: 3px;
  padding: 0 4px;
  font-size: 11.5px;
  font-family: inherit;
  width: 110px;
  outline: none;
}

.td-tab-x {
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  padding: 0 3px;
  font-size: 13px;
  line-height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}
.td-tab-x:hover { background: rgba(255, 100, 100, 0.15); color: #f78166; }

.td-newtab {
  flex-shrink: 0;
  background: transparent;
  border: 1px dashed #3a3a3a;
  color: #6b7280;
  cursor: pointer;
  border-radius: 4px;
  width: 24px;
  height: 22px;
  padding: 0;
  font-size: 15px;
  line-height: 20px;
  transition: color 0.15s, border-color 0.15s;
}
.td-newtab:hover:not(:disabled) { color: #79c0ff; border-color: #79c0ff; }
.td-newtab:disabled { opacity: 0.4; cursor: not-allowed; }

.td-spacer { flex-shrink: 0; width: 6px; }

.td-header :deep(.n-button) { color: #d4d4d4 !important; }
.td-header :deep(.n-button):hover { background: rgba(255, 255, 255, 0.06) !important; }
.td-header :deep(.n-button):disabled { color: #6b7280 !important; }

.td-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #9ca3af;
  font-size: 12px;
  padding: 20px;
}

.td-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}
/* 让 v-show 的多个 tab 实例叠在同一位置 */
.td-body :deep(.tab-instance) {
  position: absolute;
  inset: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
