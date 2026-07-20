<script setup lang="ts">
/**
 * 只读代码浏览器：从 chat-panel 右侧滑出的抽屉。
 *
 * - tab 栏：切换已打开文件；每个 tab 有关闭 ✕
 * - 内容区：复用 <CodeBlock>（Shiki 般的暗色高亮）
 * - 可拖拽调宽 / 关闭
 */
import { computed, ref } from 'vue'
import { NButton, NTooltip, NSpin } from 'naive-ui'
import CodeBlock from './CodeBlock.vue'
import ResizeHandle from './ResizeHandle.vue'
import { useCodeViewerStore } from '../stores/codeViewer'

const viewer = useCodeViewerStore()

const width = ref<number>(
  Math.min(720, Math.max(360, Math.round(window.innerWidth * 0.42))),
)

let startWidth = 0
function onResizeStart() { startWidth = width.value }
function onResize(delta: number) {
  // handle 在左侧，向左拖 → 加宽
  width.value = Math.max(320, Math.min(1000, startWidth - delta))
}

/** 显示成 "路径" 或末尾文件名 */
function tabLabel(path: string): string {
  const parts = path.split('/')
  return parts[parts.length - 1] || path
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

const active = computed(() => viewer.activeTab)
</script>

<template>
  <aside v-if="viewer.open" class="cv-panel" :style="{ width: width + 'px' }">
    <ResizeHandle side="right" @resize-start="onResizeStart" @resize="onResize" />

    <div class="cv-header">
      <span class="cv-title">📖 代码浏览器</span>
      <span class="cv-spacer" />
      <NTooltip>
        <template #trigger>
          <NButton size="tiny" quaternary @click="viewer.closeAll()">关闭全部</NButton>
        </template>
        关闭所有 tab 并收起面板
      </NTooltip>
      <NTooltip>
        <template #trigger>
          <NButton size="tiny" quaternary @click="viewer.hideViewer()">×</NButton>
        </template>
        收起面板（保留已打开 tab）
      </NTooltip>
    </div>

    <div class="cv-tabs" v-if="viewer.tabs.length">
      <div
        v-for="t in viewer.tabs"
        :key="t.path"
        class="cv-tab"
        :class="{ active: t.path === viewer.activePath }"
        :title="t.path"
        @click="viewer.switchTab(t.path)"
      >
        <span class="cv-tab-name">{{ tabLabel(t.path) }}</span>
        <button class="cv-tab-x" @click.stop="viewer.closeTab(t.path)">✕</button>
      </div>
    </div>

    <div class="cv-body">
      <div v-if="!active" class="cv-empty">
        <p>双击右侧文件树中的文件在这里预览。</p>
        <p class="hint">或右键选择"用浏览器打开"</p>
      </div>
      <template v-else>
        <div class="cv-meta">
          <code class="cv-path">{{ active.path }}</code>
          <span class="cv-size">{{ formatSize(active.size) }}</span>
          <span v-if="active.truncated" class="cv-trunc">已截断</span>
        </div>
        <div v-if="active.loading" class="cv-loading">
          <NSpin size="small" /> 加载中…
        </div>
        <div v-else-if="active.error" class="cv-error">
          ⚠️ {{ active.error }}
        </div>
        <CodeBlock
          v-else
          :code="active.content"
          :filename="active.path"
          max-height="calc(100vh - 200px)"
        />
      </template>
    </div>
  </aside>
</template>

<style scoped>
.cv-panel {
  position: relative;
  border-left: 1px solid #e5e7eb;
  background: #fafbfc;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  min-width: 320px;
}

.cv-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #ececec;
  background: white;
  flex-shrink: 0;
}

.cv-title {
  font-weight: 600;
  font-size: 13px;
  color: #1f2937;
}

.cv-spacer { flex: 1; }

.cv-tabs {
  display: flex;
  gap: 2px;
  padding: 4px 8px 0;
  background: #f3f4f6;
  border-bottom: 1px solid #e5e7eb;
  overflow-x: auto;
  flex-shrink: 0;
}

.cv-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px 5px 12px;
  background: #e5e7eb;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  color: #4b5563;
  white-space: nowrap;
  transition: background 0.1s;
  flex-shrink: 0;
  max-width: 200px;
}
.cv-tab:hover { background: #eef2f7; color: #1f2937; }
.cv-tab.active {
  background: white;
  color: #1677ff;
  border-color: #e5e7eb;
}

.cv-tab-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cv-tab-x {
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  padding: 0 3px;
  font-size: 10px;
  border-radius: 3px;
}
.cv-tab-x:hover { background: #fee2e2; color: #dc2626; }

.cv-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 8px 12px 12px;
  background: white;
}

.cv-empty {
  color: #9ca3af;
  text-align: center;
  padding: 60px 20px;
  font-size: 13px;
}
.cv-empty .hint {
  font-size: 12px;
  color: #d1d5db;
  margin-top: 6px;
}

.cv-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 11px;
  color: #6b7280;
}
.cv-path {
  font-family: 'SF Mono', 'Monaco', monospace;
  color: #1f2937;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  flex: 1;
  min-width: 0;
}
.cv-size {
  flex-shrink: 0;
  font-family: 'SF Mono', 'Monaco', monospace;
}
.cv-trunc {
  color: #b45309;
  background: #fef3c7;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
  flex-shrink: 0;
}

.cv-loading, .cv-error {
  padding: 30px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.cv-error { color: #b91c1c; }
</style>
