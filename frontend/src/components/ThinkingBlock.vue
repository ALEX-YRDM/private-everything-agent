<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ content: string }>()
const expanded = ref(false)
</script>

<template>
  <div class="thinking-block">
    <div class="thinking-header" @click="expanded = !expanded">
      <span class="thinking-icon">🧠</span>
      <span class="thinking-label">思维过程</span>
      <span class="toggle-icon">{{ expanded ? '▲' : '▼' }}</span>
    </div>
    <div v-if="expanded" class="thinking-content">
      <pre>{{ content }}</pre>
    </div>
  </div>
</template>

<style scoped>
.thinking-block {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
  background: #fafafa;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  color: #666;
}

.thinking-header:hover {
  background: #f0f0f0;
}

.thinking-icon {
  font-size: 14px;
}

.thinking-label {
  flex: 1;
  font-weight: 500;
}

.toggle-icon {
  font-size: 11px;
}

.thinking-content {
  padding: 8px 12px;
  border-top: 1px solid #e0e0e0;
}

.thinking-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  color: #555;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
}
</style>
