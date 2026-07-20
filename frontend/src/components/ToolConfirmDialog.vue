<script setup lang="ts">
import { ref, computed } from 'vue'
import { NButton, NTag, NSpace, NTooltip } from 'naive-ui'
import type { PendingConfirm } from '../stores/chat'
import type { ConfirmDecision } from '../api/websocket'

const props = defineProps<{
  confirm: PendingConfirm
}>()
const emit = defineEmits<{
  decide: [decision: ConfirmDecision, extra?: string]
}>()

const expanded = ref(false)

const kind = computed(() => props.confirm.preview?.kind ?? 'file')

const previewText = computed(() => {
  const p = props.confirm.preview
  if (!p) return ''
  if (p.kind === 'exec') return `$ ${p.command}\n  (cwd: ${p.cwd})`
  if (p.kind === 'file') return `文件: ${p.path}\n\n参数：\n${JSON.stringify(props.confirm.args, null, 2)}`
  if (p.kind === 'patch') return p.patch
  return JSON.stringify(props.confirm.args, null, 2)
})

function decide(d: ConfirmDecision, extra?: string) {
  emit('decide', d, extra)
}
</script>

<template>
  <div class="confirm-card" :class="kind">
    <div class="confirm-header" @click="expanded = !expanded">
      <span class="confirm-icon">🔒</span>
      <span class="confirm-title">
        需要确认：
        <code class="tool-name">{{ confirm.name }}</code>
      </span>
      <NTag size="tiny" type="warning" style="margin-left: 6px">等待中</NTag>
      <span class="expand-toggle">{{ expanded ? '▲' : '▼' }}</span>
    </div>

    <div class="confirm-why">{{ confirm.why }}</div>

    <div v-if="expanded" class="confirm-preview">
      <pre>{{ previewText }}</pre>
    </div>

    <div class="confirm-actions">
      <NSpace size="small">
        <NButton type="primary" size="small" @click="decide('allow')">允许</NButton>
        <NButton type="error" ghost size="small" @click="decide('deny')">拒绝</NButton>
        <NTooltip v-if="confirm.suggested_trust_path">
          <template #trigger>
            <NButton size="small" @click="decide('trust_path', confirm.suggested_trust_path)">
              信任目录
            </NButton>
          </template>
          将 <code>{{ confirm.suggested_trust_path }}</code> 加入会话信任列表，
          后续同目录下的操作不再询问
        </NTooltip>
        <NTooltip v-if="confirm.suggested_trust_command">
          <template #trigger>
            <NButton size="small" @click="decide('trust_command', confirm.suggested_trust_command)">
              信任命令 <code>{{ confirm.suggested_trust_command }}</code>
            </NButton>
          </template>
          后续以 "{{ confirm.suggested_trust_command }}" 开头的命令不再询问
        </NTooltip>
      </NSpace>
    </div>
  </div>
</template>

<style scoped>
.confirm-card {
  border: 1px solid #ffd591;
  background: #fffbe6;
  border-radius: 10px;
  padding: 10px 12px;
  margin: 8px 0;
  font-size: 13px;
}
.confirm-card.exec { border-color: #ffa39e; background: #fff2f0; }
.confirm-card.patch { border-color: #91caff; background: #e6f4ff; }

.confirm-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}
.confirm-icon { font-size: 14px; }
.confirm-title {
  font-weight: 600;
  color: #333;
  flex: 1;
}
.tool-name {
  font-family: 'SF Mono', 'Monaco', monospace;
  color: #1677ff;
  background: rgba(22, 119, 255, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.expand-toggle {
  color: #999;
  font-size: 10px;
}

.confirm-why {
  color: #666;
  font-size: 12px;
  margin: 6px 0;
  line-height: 1.5;
}

.confirm-preview {
  border-top: 1px dashed #e8e8e8;
  padding-top: 8px;
  margin-top: 6px;
}
.confirm-preview pre {
  margin: 0;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #333;
  max-height: 260px;
  overflow-y: auto;
  background: rgba(255, 255, 255, 0.65);
  padding: 6px 8px;
  border-radius: 4px;
}

.confirm-actions {
  margin-top: 8px;
}
</style>
