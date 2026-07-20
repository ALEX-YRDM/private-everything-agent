<script setup lang="ts">
import { computed } from 'vue'

export interface MentionCandidate {
  path: string
  name: string
}

const props = defineProps<{
  candidates: MentionCandidate[]
  activeIndex: number
  loading?: boolean
  query: string
  /** 相对 ChatPanel 的坐标（left/bottom；下拉挂在输入框上方，用 bottom 撑起来） */
  anchorLeft: number
  anchorBottom: number
}>()

const emit = defineEmits<{
  pick: [candidate: MentionCandidate]
  hoverIndex: [index: number]
}>()

const hasResults = computed(() => props.candidates.length > 0)

/** 高亮匹配子串 */
function highlight(name: string): string {
  if (!props.query) return escape(name)
  const q = props.query.toLowerCase()
  const idx = name.toLowerCase().indexOf(q)
  if (idx < 0) return escape(name)
  return escape(name.slice(0, idx)) +
    `<mark class="mp-hl">${escape(name.slice(idx, idx + q.length))}</mark>` +
    escape(name.slice(idx + q.length))
}
function escape(s: string): string {
  return s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] || c))
}
</script>

<template>
  <div
    class="mention-popover"
    :style="{ left: anchorLeft + 'px', bottom: anchorBottom + 'px' }"
    @mousedown.prevent
  >
    <div class="mp-header">
      <span>引用文件</span>
      <span v-if="query" class="mp-query">"{{ query }}"</span>
    </div>
    <div v-if="loading && !hasResults" class="mp-hint">搜索中…</div>
    <div v-else-if="!hasResults" class="mp-hint">无匹配</div>
    <div v-else class="mp-list">
      <div
        v-for="(c, i) in candidates"
        :key="c.path"
        class="mp-item"
        :class="{ active: i === activeIndex }"
        @mouseenter="emit('hoverIndex', i)"
        @click="emit('pick', c)"
      >
        <span class="mp-name" v-html="highlight(c.name)"></span>
        <span class="mp-path">{{ c.path }}</span>
      </div>
    </div>
    <div class="mp-footer">↑↓ 移动 · ⏎ 附加 · Esc 取消</div>
  </div>
</template>

<style scoped>
.mention-popover {
  position: absolute;
  z-index: 100;
  width: 380px;
  max-width: 92vw;
  background: white;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 4px 0;
  font-size: 12px;
}

.mp-header {
  padding: 6px 12px 4px;
  color: #6b7280;
  font-size: 11px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1px solid #f3f4f6;
}
.mp-query {
  font-family: 'SF Mono', 'Monaco', monospace;
  color: #1f2937;
  background: #f3f4f6;
  padding: 1px 5px;
  border-radius: 3px;
}

.mp-hint {
  padding: 12px;
  color: #9ca3af;
  text-align: center;
}

.mp-list {
  max-height: 280px;
  overflow-y: auto;
}

.mp-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 12px;
  cursor: pointer;
  transition: background 0.1s;
}
.mp-item:hover,
.mp-item.active {
  background: #eef4ff;
}

.mp-name {
  font-family: 'SF Mono', 'Monaco', monospace;
  color: #1f2937;
  font-size: 12px;
  flex-shrink: 0;
}
:deep(.mp-hl) {
  background: rgba(22, 119, 255, 0.18);
  color: #1e40af;
  padding: 0;
  border-radius: 2px;
}

.mp-path {
  color: #9ca3af;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.mp-footer {
  padding: 4px 12px;
  color: #9ca3af;
  font-size: 10.5px;
  border-top: 1px solid #f3f4f6;
}
</style>
