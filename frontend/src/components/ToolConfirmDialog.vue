<script setup lang="ts">
import { ref, computed } from 'vue'
import { NButton, NSpace, NTooltip } from 'naive-ui'
import type { PendingConfirm } from '../stores/chat'
import type { ConfirmDecision } from '../api/websocket'

const props = defineProps<{
  confirm: PendingConfirm
}>()
const emit = defineEmits<{
  decide: [decision: ConfirmDecision, extra?: string]
}>()

const expanded = ref(true)

const kind = computed(() => props.confirm.preview?.kind ?? 'file')

const previewText = computed(() => {
  const p = props.confirm.preview
  if (!p) return JSON.stringify(props.confirm.args, null, 2)
  if (p.kind === 'exec') return `$ ${p.command}`
  if (p.kind === 'file') return JSON.stringify(props.confirm.args, null, 2)
  if (p.kind === 'patch') return p.patch
  return JSON.stringify(props.confirm.args, null, 2)
})

const icon = computed(() => {
  if (kind.value === 'exec') return '⚡'
  if (kind.value === 'patch') return '🩹'
  return '📝'
})

const kindLabel = computed(() => {
  if (kind.value === 'exec') return 'Shell 命令'
  if (kind.value === 'patch') return 'Diff 补丁'
  return '文件修改'
})

function decide(d: ConfirmDecision, extra?: string) {
  emit('decide', d, extra)
}
</script>

<template>
  <div class="confirm-card" :class="[`kind-${kind}`]">
    <div class="cc-head" @click="expanded = !expanded">
      <span class="cc-icon">{{ icon }}</span>
      <div class="cc-head-text">
        <div class="cc-title">
          需要你的许可执行
          <code class="cc-tool-name">{{ confirm.name }}</code>
          <span class="cc-kind-tag">{{ kindLabel }}</span>
        </div>
        <div class="cc-why">{{ confirm.why }}</div>
      </div>
      <span class="cc-toggle">{{ expanded ? '▾' : '▸' }}</span>
    </div>

    <div v-if="expanded" class="cc-body">
      <div v-if="confirm.cwd" class="cc-cwd">
        <span class="cc-cwd-label">目录</span>
        <code>{{ confirm.cwd }}</code>
      </div>
      <pre class="cc-preview">{{ previewText }}</pre>
    </div>

    <div class="cc-actions">
      <NSpace size="small">
        <NButton type="primary" size="small" @click="decide('allow')">
          允许一次
        </NButton>
        <NButton size="small" @click="decide('deny')">拒绝</NButton>
        <NTooltip v-if="confirm.suggested_trust_command">
          <template #trigger>
            <NButton
              size="small"
              secondary
              @click="decide('trust_command', confirm.suggested_trust_command)"
            >
              信任 <code>{{ confirm.suggested_trust_command }}</code> 前缀
            </NButton>
          </template>
          后续以 "{{ confirm.suggested_trust_command }}" 开头的命令不再询问
        </NTooltip>
        <NTooltip v-if="confirm.suggested_trust_path">
          <template #trigger>
            <NButton
              size="small"
              secondary
              @click="decide('trust_path', confirm.suggested_trust_path)"
            >
              信任此目录
            </NButton>
          </template>
          将 <code>{{ confirm.suggested_trust_path }}</code> 加入信任列表
        </NTooltip>
      </NSpace>
    </div>
  </div>
</template>

<style scoped>
.confirm-card {
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 10px;
  margin: 8px 0;
  font-size: 13px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}
.confirm-card.kind-exec { border-color: #fdba74; }
.confirm-card.kind-file { border-color: #fde68a; }
.confirm-card.kind-patch { border-color: #93c5fd; }

.cc-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
  background: linear-gradient(180deg, #fffdf8 0%, #ffffff 100%);
  transition: background 0.15s;
}
.confirm-card.kind-exec .cc-head  { background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%); }
.confirm-card.kind-patch .cc-head { background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%); }
.cc-head:hover { filter: brightness(0.99); }

.cc-icon {
  font-size: 20px;
  line-height: 22px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: white;
  border: 1px solid #e5e7eb;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cc-head-text {
  flex: 1;
  min-width: 0;
}

.cc-title {
  font-weight: 600;
  color: #1f2937;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.cc-tool-name {
  font-family: 'SF Mono', 'Monaco', monospace;
  color: #1677ff;
  background: rgba(22, 119, 255, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.cc-kind-tag {
  font-size: 11px;
  font-weight: 500;
  color: #6b7280;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 4px;
}

.cc-why {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 2px;
}

.cc-toggle {
  color: #9ca3af;
  font-size: 11px;
  flex-shrink: 0;
  padding-top: 4px;
}

.cc-body {
  padding: 0 12px 8px 48px;  /* 与 head 里 icon 后的内容左对齐 */
  border-top: 1px dashed #f0f0f0;
}

.cc-cwd {
  font-size: 11px;
  color: #6b7280;
  margin: 8px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.cc-cwd-label {
  color: #9ca3af;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-size: 10px;
}
.cc-cwd code {
  font-family: 'SF Mono', 'Monaco', monospace;
  color: #1f2937;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  word-break: break-all;
}

.cc-preview {
  margin: 6px 0 0;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  font-size: 12px;
  color: #1f2937;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 280px;
  overflow-y: auto;
  line-height: 1.5;
}

.cc-actions {
  padding: 10px 12px 12px 48px;
  border-top: 1px solid #f3f4f6;
  background: #fcfcfd;
}
</style>
