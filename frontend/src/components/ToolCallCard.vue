<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCallDisplay } from '../stores/chat'

const props = defineProps<{
  toolCall: ToolCallDisplay
  result?: string
}>()

const expanded = ref(false)

const status = computed(() => {
  if (props.result !== undefined) return 'done'
  return 'running'
})

const statusText = computed(() => {
  if (status.value === 'done') return '完成'
  return '执行中…'
})

const toolIcon: Record<string, string> = {
  read_file: '📄',
  write_file: '✏️',
  edit_file: '🔧',
  list_dir: '📁',
  exec: '⚡',
  web_search: '🔍',
  web_fetch: '🌐',
}

const icon = computed(() => {
  for (const key of Object.keys(toolIcon)) {
    if (props.toolCall.name.includes(key)) return toolIcon[key]
  }
  return '🔧'
})
</script>

<template>
  <div class="tool-card" :class="status">
    <div class="tool-header" @click="expanded = !expanded">
      <span class="tool-icon">{{ icon }}</span>
      <span class="tool-name">{{ toolCall.name }}</span>
      <span class="status-badge" :class="status">{{ statusText }}</span>
      <span class="toggle-icon">{{ expanded ? '▲' : '▼' }}</span>
    </div>
    <div v-if="expanded" class="tool-body">
      <div class="tool-args">
        <div class="section-label">参数</div>
        <pre>{{ JSON.stringify(toolCall.args, null, 2) }}</pre>
      </div>
      <div v-if="result !== undefined" class="tool-result">
        <div class="section-label">结果</div>
        <pre>{{ result }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin-bottom: 6px;
  overflow: hidden;
}

.tool-card.done {
  border-color: #d0e8d0;
}

.tool-card.running {
  border-color: #ffd57a;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  background: #f9f9f9;
  font-size: 13px;
  user-select: none;
}

.tool-card.done .tool-header {
  background: #f0f8f0;
}

.tool-card.running .tool-header {
  background: #fffbf0;
}

.tool-header:hover {
  filter: brightness(0.97);
}

.tool-name {
  flex: 1;
  font-weight: 600;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  font-size: 12px;
}

.status-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 10px;
}

.status-badge.done {
  background: #d4edda;
  color: #155724;
}

.status-badge.running {
  background: #fff3cd;
  color: #856404;
}

.toggle-icon {
  font-size: 10px;
  color: #999;
}

.tool-body {
  border-top: 1px solid #e8e8e8;
}

.tool-args, .tool-result {
  padding: 8px 12px;
}

.tool-result {
  border-top: 1px solid #f0f0f0;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  color: #444;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  max-height: 300px;
  overflow-y: auto;
}
</style>
