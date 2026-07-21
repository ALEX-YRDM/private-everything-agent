<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'
import CodeBlock from './CodeBlock.vue'
import DiffView from './DiffView.vue'
import { copyToClipboard } from '../utils/clipboard'
import { pickToolPreview } from '../utils/toolPreview'
import type { ToolCallDisplay } from '../stores/chat'

const props = defineProps<{
  toolCall: ToolCallDisplay
  result?: string
}>()

const msg = useMessage()
const justCopied = ref(false)

async function copyResult() {
  if (props.result === undefined) return
  await copyToClipboard(
    props.result,
    undefined,
    () => {
      msg.success('结果已复制')
      justCopied.value = true
      setTimeout(() => { justCopied.value = false }, 1200)
    },
    (error) => msg.error(`复制失败: ${error.message}`)
  )
}

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
  multi_edit: '🔧',
  apply_patch: '🩹',
  list_dir: '📁',
  glob: '🔎',
  grep: '🔍',
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

const targetPath = computed<string | undefined>(() => {
  const args = props.toolCall.args as Record<string, unknown> | undefined
  const p = args?.path ?? args?.file_path
  return typeof p === 'string' ? p : undefined
})

/** 参数区的智能展示：edit/multi_edit → diff，write_file/exec → 高亮 code */
const argsPreview = computed(() =>
  pickToolPreview(props.toolCall.name, props.toolCall.args as Record<string, any>),
)

/** 结果区展示：apply_patch/multi_edit 返回内容有时也是 diff；否则按 filename 高亮 */
const resultView = computed<'diff' | 'code'>(() => {
  if (!props.result) return 'code'
  const name = props.toolCall.name
  if (name.includes('apply_patch')) return 'diff'
  if (props.result.startsWith('--- ') && props.result.includes('\n+++ ')) return 'diff'
  return 'code'
})

const resultLang = computed<string | undefined>(() => {
  const name = props.toolCall.name
  if (name === 'exec') return 'bash'
  if (name === 'grep' || name === 'glob' || name.includes('list_dir')) return 'plaintext'
  return undefined
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
        <div class="section-label">
          参数
          <span v-if="targetPath" class="tool-target-path" :title="targetPath">📁 {{ targetPath }}</span>
        </div>

        <!-- 参数流式生成中：显示原文 -->
        <pre v-if="toolCall.streamingArgs !== undefined">{{ toolCall.streamingArgs }}<span class="cursor-blink">▋</span></pre>

        <!-- edit_file / multi_edit / apply_patch → diff -->
        <DiffView
          v-else-if="argsPreview?.kind === 'diff'"
          :patch="argsPreview.patch"
          max-height="360px"
        />

        <!-- write_file / exec → 语法高亮 -->
        <CodeBlock
          v-else-if="argsPreview?.kind === 'code'"
          :code="argsPreview.code"
          :lang="argsPreview.lang"
          :filename="argsPreview.filename"
          max-height="360px"
        />

        <!-- 其他：格式化 JSON 展示 -->
        <CodeBlock
          v-else
          :code="JSON.stringify(toolCall.args, null, 2)"
          lang="json"
          max-height="200px"
        />
      </div>
      <div v-if="result !== undefined" class="tool-result">
        <div class="result-header">
          <div class="section-label">结果</div>
          <button
            class="copy-result-btn"
            :class="{ copied: justCopied }"
            type="button"
            title="复制结果（原始文本）"
            @click="copyResult"
          >📋</button>
        </div>
        <DiffView v-if="resultView === 'diff'" :patch="result" max-height="360px" />
        <CodeBlock
          v-else
          :code="result"
          :lang="resultLang"
          :filename="targetPath"
          max-height="360px"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-card {
  position: relative;
  border: 1px solid var(--md-border-soft);
  border-radius: var(--md-radius-md);
  margin-bottom: 8px;
  overflow: hidden;
  background: var(--md-bg);
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}

.tool-card:hover {
  box-shadow: var(--md-shadow-sm);
}

/* 左侧状态色条 */
.tool-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--md-brand);
  transition: background 0.2s ease;
}

.tool-card.done::before {
  background: var(--md-success);
}

.tool-card.running::before {
  background: var(--md-warning);
}

.tool-card.done {
  border-color: #d1fae5;
}

.tool-card.running {
  border-color: #fde68a;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 8px 15px;
  cursor: pointer;
  background: var(--md-bg-subtle);
  font-size: 13px;
  user-select: none;
  transition: background 0.15s ease;
}

.tool-card.done .tool-header {
  background: linear-gradient(90deg, var(--md-success-soft) 0%, rgba(240, 253, 244, 0.4) 60%, var(--md-bg) 100%);
}

.tool-card.running .tool-header {
  background: linear-gradient(90deg, var(--md-warning-soft) 0%, rgba(254, 249, 195, 0.4) 60%, var(--md-bg) 100%);
}

.tool-header:hover {
  filter: brightness(0.98);
}

.tool-name {
  flex: 1;
  font-weight: 600;
  font-family: var(--md-font-mono);
  font-size: 12px;
  color: var(--md-text-primary);
}

.status-badge {
  font-size: 10.5px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.status-badge.done {
  background: var(--md-success-soft);
  color: var(--md-success);
}

.status-badge.running {
  background: var(--md-warning-soft);
  color: var(--md-warning);
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
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-target-path {
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 11px;
  font-weight: 400;
  color: #6b7280;
  text-transform: none;
  letter-spacing: 0;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.copy-result-btn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 12px;
  color: #888;
  cursor: pointer;
  opacity: 0.55;
  transition: opacity 0.2s, background 0.2s, color 0.2s, border-color 0.2s;
}

.tool-result:hover .copy-result-btn {
  opacity: 1;
}

.copy-result-btn:hover {
  background: #f0f0f0;
  color: #333;
}

.copy-result-btn.copied {
  background: #f6ffed;
  color: #52c41a;
  border-color: #b7eb8f;
  opacity: 1;
}

@media (hover: none) and (pointer: coarse) {
  .copy-result-btn { opacity: 1; }
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

.cursor-blink {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: #1677ff;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
