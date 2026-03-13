<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTag, NCollapse, NCollapseItem } from 'naive-ui'
import type { SubAgentState } from '../stores/chat'
import type { SubAgentInnerEvent } from '../api/websocket'

const props = defineProps<{
  subAgent: SubAgentState
}>()

const expanded = ref(false)

const statusType = computed(() => {
  if (props.subAgent.status === 'completed') return 'success'
  if (props.subAgent.status === 'failed') return 'error'
  return 'warning'
})

const statusText = computed(() => {
  if (props.subAgent.status === 'completed') return '已完成'
  if (props.subAgent.status === 'failed') return '失败'
  return '执行中…'
})

// 从内部事件提取工具调用（用于展开显示）
const toolCallEvents = computed(() =>
  props.subAgent.events.filter((e): e is Extract<SubAgentInnerEvent, { type: 'tool_call' }> =>
    e.type === 'tool_call'
  )
)

const contentEvents = computed(() =>
  props.subAgent.events.filter(
    (e): e is Extract<SubAgentInnerEvent, { type: 'content_delta' }> =>
      e.type === 'content_delta'
  )
)

const accumulatedContent = computed(() =>
  contentEvents.value.map((e) => e.content).join('')
)
</script>

<template>
  <div class="subagent-block" :class="subAgent.status">
    <!-- 头部：点击展开/收起 -->
    <div class="subagent-header" @click="expanded = !expanded">
      <span class="subagent-icon">
        <span v-if="subAgent.status === 'running'" class="spinner">⟳</span>
        <span v-else-if="subAgent.status === 'completed'">✓</span>
        <span v-else>✗</span>
      </span>
      <span class="subagent-label">SubAgent</span>
      <span class="subagent-task">{{ subAgent.task }}</span>
      <NTag :type="statusType" size="tiny" class="status-tag">{{ statusText }}</NTag>
      <span class="expand-icon">{{ expanded ? '▲' : '▼' }}</span>
    </div>

    <!-- 展开内容 -->
    <div v-if="expanded" class="subagent-body">
      <!-- 工具调用列表 -->
      <div v-if="toolCallEvents.length > 0" class="tool-calls-section">
        <div v-for="tc in toolCallEvents" :key="tc.id" class="inner-tool-call">
          <span class="tool-call-icon">⚙</span>
          <span class="tool-call-name">{{ tc.name }}</span>
          <span v-if="Object.keys(tc.args).length > 0" class="tool-call-args">
            {{ JSON.stringify(tc.args).slice(0, 80) }}{{ JSON.stringify(tc.args).length > 80 ? '…' : '' }}
          </span>
        </div>
      </div>

      <!-- 最终结果 -->
      <div v-if="subAgent.result" class="subagent-result">
        <div class="result-label">返回结果</div>
        <div class="result-content">{{ subAgent.result }}</div>
      </div>

      <!-- 错误信息 -->
      <div v-if="subAgent.error" class="subagent-error">
        <span class="error-label">错误：</span>{{ subAgent.error }}
      </div>

      <!-- 无内容提示 -->
      <div
        v-if="!toolCallEvents.length && !subAgent.result && !subAgent.error"
        class="subagent-empty"
      >
        <span v-if="subAgent.status === 'running'">执行中，等待结果…</span>
        <span v-else>无详细信息</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subagent-block {
  margin: 6px 0;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
  overflow: hidden;
  font-size: 13px;
  background: #fafafa;
}

.subagent-block.running {
  border-color: #faad14;
  background: #fffbe6;
}

.subagent-block.completed {
  border-color: #b7eb8f;
  background: #f6ffed;
}

.subagent-block.failed {
  border-color: #ffccc7;
  background: #fff2f0;
}

.subagent-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  cursor: pointer;
  user-select: none;
  min-height: 34px;
}

.subagent-header:hover {
  background: rgba(0, 0, 0, 0.03);
}

.subagent-icon {
  font-size: 14px;
  width: 16px;
  text-align: center;
  flex-shrink: 0;
}

.spinner {
  display: inline-block;
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.subagent-label {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.subagent-task {
  flex: 1;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.status-tag {
  flex-shrink: 0;
}

.expand-icon {
  font-size: 10px;
  color: #aaa;
  flex-shrink: 0;
}

/* 展开内容 */
.subagent-body {
  border-top: 1px solid #e8e8e8;
  padding: 8px 12px;
}

.tool-calls-section {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 8px;
}

.inner-tool-call {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 4px;
  font-size: 12px;
}

.tool-call-icon {
  color: #666;
  flex-shrink: 0;
}

.tool-call-name {
  font-family: monospace;
  color: #1677ff;
  flex-shrink: 0;
}

.tool-call-args {
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subagent-result {
  margin-top: 4px;
}

.result-label {
  font-size: 11px;
  font-weight: 600;
  color: #52c41a;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.result-content {
  color: #333;
  font-size: 12px;
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
  background: white;
  border-radius: 4px;
  padding: 6px 8px;
  border: 1px solid #e8e8e8;
}

.subagent-error {
  color: #ff4d4f;
  font-size: 12px;
  margin-top: 4px;
}

.error-label {
  font-weight: 600;
}

.subagent-empty {
  color: #aaa;
  font-size: 12px;
  text-align: center;
  padding: 4px 0;
}
</style>
