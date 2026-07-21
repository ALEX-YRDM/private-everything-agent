<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMessage, NInput, NButton } from 'naive-ui'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallCard from './ToolCallCard.vue'
import { renderMarkdown } from '../utils/markdown'
import { copyToClipboard } from '../utils/clipboard'
import type { DisplayMessage } from '../stores/chat'
import { useChatStore } from '../stores/chat'

const props = defineProps<{ message: DisplayMessage }>()

const chat = useChatStore()
const msg = useMessage()

// 编辑态：只对已持久化的历史 user 消息（id = "msg-<int>"）开放
const editing = ref(false)
const editText = ref('')
const canEdit = computed(() =>
  props.message.role === 'user' && /^msg-\d+$/.test(props.message.id) && !chat.isStreaming,
)

function startEdit() {
  editText.value = props.message.content || ''
  editing.value = true
}
function cancelEdit() { editing.value = false }
async function commitEdit() {
  const text = editText.value.trim()
  if (!text) { cancelEdit(); return }
  editing.value = false
  try {
    await chat.editAndResendFrom(props.message.id, text)
  } catch (e: any) {
    msg.error(`重发失败：${e?.message || e}`)
  }
}

const previewImage = ref<string | null>(null)
const userCopied = ref(false)
const assistantCopied = ref(false)

const formattedTime = computed(() => {
  return new Date(props.message.timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
})

const renderedContent = computed(() => renderMarkdown(props.message.content))

const ERROR_META: Record<string, { icon: string; title: string }> = {
  LLM_AUTH:              { icon: '🔑', title: 'API Key 无效' },
  LLM_RATE_LIMIT:        { icon: '⏳', title: '触发速率限制' },
  LLM_CONTEXT_OVERFLOW:  { icon: '📚', title: '上下文超限' },
  LLM_MODEL_NOT_FOUND:   { icon: '❓', title: '模型不存在' },
  LLM_TIMEOUT:           { icon: '⏱️', title: '请求超时' },
  LLM_UNKNOWN:           { icon: '⚠️', title: '大模型调用失败' },
  TOOL_PERMISSION_DENIED:{ icon: '🚫', title: '操作被拒绝' },
  TOOL_PATH_INVALID:     { icon: '📁', title: '路径非法' },
  TOOL_EXEC_FAILED:      { icon: '💥', title: '工具执行失败' },
  TOOL_TIMEOUT:          { icon: '⏱️', title: '工具超时' },
}

const errorMeta = computed(() => {
  const cat = props.message.errorCategory
  if (cat && ERROR_META[cat]) return ERROR_META[cat]!
  return ERROR_META.LLM_UNKNOWN!
})
const errorIcon = computed(() => errorMeta.value.icon)
const errorTitle = computed(() => errorMeta.value.title)

function formatFileSize(bytes?: number): string {
  if (bytes == null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

async function copyUserMessage() {
  await copyToClipboard(
    props.message.content,
    undefined,
    () => {
      msg.success('已复制到剪切板')
      userCopied.value = true
      setTimeout(() => { userCopied.value = false }, 1200)
    },
    (error) => msg.error(`复制失败: ${error.message}`)
  )
}

async function copyAssistantMessage() {
  const plainText = props.message.content
  const html = renderedContent.value

  await copyToClipboard(
    plainText,
    html,
    () => {
      msg.success('已复制到剪切板')
      assistantCopied.value = true
      setTimeout(() => { assistantCopied.value = false }, 1200)
    },
    (error) => msg.error(`复制失败: ${error.message}`)
  )
}

async function handleMarkdownClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const btn = target.closest('.code-copy-btn') as HTMLButtonElement | null
  if (!btn) return
  const wrapper = btn.closest('.code-block-wrapper')
  const code = wrapper?.querySelector('code')?.textContent ?? ''
  await copyToClipboard(
    code,
    undefined,
    () => {
      msg.success('代码已复制')
      btn.classList.add('copied')
      setTimeout(() => btn.classList.remove('copied'), 1200)
    },
    (error) => msg.error(`复制失败: ${error.message}`)
  )
}
</script>

<template>
  <div class="message-wrapper" :class="message.role">
    <div class="message-bubble" :class="message.role">
      <template v-if="message.role === 'user'">
        <div v-if="message.images?.length" class="user-images">
          <img
            v-for="(img, idx) in message.images"
            :key="idx"
            :src="img"
            class="user-image-thumb"
            @click="previewImage = img"
          />
        </div>
        <div v-if="message.files?.length" class="user-files">
          <div v-for="(file, idx) in message.files" :key="idx" class="file-item">
            <span class="file-icon">📎</span>
            <span class="file-name-text">{{ file.name }}</span>
            <span v-if="file.size != null" class="file-size">{{ formatFileSize(file.size) }}</span>
          </div>
        </div>
        <div v-if="message.attachedPaths?.length" class="user-attached-paths">
          <span class="uap-label">📎 引用</span>
          <code v-for="p in message.attachedPaths" :key="p" class="uap-path" :title="p">{{ p }}</code>
        </div>
        <template v-if="editing">
          <NInput
            v-model:value="editText"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 10 }"
            class="edit-input"
            @keydown.enter.exact.prevent="commitEdit"
            @keydown.esc="cancelEdit"
            autofocus
          />
          <div class="edit-actions">
            <NButton size="tiny" @click="cancelEdit">取消</NButton>
            <NButton size="tiny" type="primary" @click="commitEdit">
              重发（Enter）
            </NButton>
          </div>
        </template>
        <template v-else>
          <div class="user-content">{{ message.content }}</div>
        </template>
      </template>

      <template v-else-if="message.role === 'assistant'">
        <ThinkingBlock v-if="message.reasoning" :content="message.reasoning" />
        <ToolCallCard
          v-for="tc in message.toolCalls"
          :key="tc.id"
          :tool-call="tc"
          :result="message.toolResults?.[tc.id]"
        />
        <div
          v-if="message.content"
          class="markdown-content"
          v-html="renderedContent"
          @click="handleMarkdownClick"
        />
        <span v-if="message.isStreaming" class="cursor-blink">▋</span>
      </template>

      <template v-else-if="message.role === 'error'">
        <div class="error-content">
          <span class="error-icon">{{ errorIcon }}</span>
          <div class="error-text">
            <div class="error-title">{{ errorTitle }}</div>
            <div v-if="message.errorHint" class="error-hint">{{ message.errorHint }}</div>
            <div class="error-message">{{ message.content }}</div>
          </div>
        </div>
      </template>
    </div>
    <div class="message-meta">
      <button
        v-if="message.role === 'user' && message.content"
        class="copy-btn"
        :class="{ copied: userCopied }"
        type="button"
        @click="copyUserMessage"
        :title="userCopied ? '已复制' : '复制到剪切板'"
      >{{ userCopied ? '✅' : '📋' }}</button>
      <button
        v-if="canEdit && !editing"
        class="copy-btn edit-btn"
        type="button"
        @click="startEdit"
        title="编辑并从此处重发"
      >✏️</button>
      <span class="message-time">{{ formattedTime }}</span>
      <span
        v-if="message.role === 'assistant' && (message.inputTokens != null || message.outputTokens != null)"
        class="token-info"
      >· ↑{{ message.inputTokens?.toLocaleString() ?? '—' }} ↓{{ message.outputTokens?.toLocaleString() ?? '—' }}</span>
      <button
        v-if="message.role === 'assistant' && message.content"
        class="copy-btn"
        :class="{ copied: assistantCopied }"
        type="button"
        @click="copyAssistantMessage"
        :title="assistantCopied ? '已复制' : '复制到剪切板'"
      >{{ assistantCopied ? '✅' : '📋' }}</button>
    </div>
  </div>

  <!-- 图片预览遮罩 -->
  <Teleport to="body">
    <div v-if="previewImage" class="image-preview-overlay" @click="previewImage = null">
      <img :src="previewImage" class="image-preview-full" />
    </div>
  </Teleport>
</template>

<style scoped>
.message-wrapper {
  display: flex;
  flex-direction: column;
  margin-bottom: 18px;
  /* 消息进入动画 */
  animation: msg-in 220ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-wrapper.user {
  align-items: flex-end;
}

.message-wrapper.assistant {
  align-items: flex-start;
}

.message-wrapper.error {
  align-items: stretch;
}

.message-bubble.error {
  max-width: 100%;
  background: linear-gradient(180deg, #fff5f5 0%, #fff2f0 100%);
  border: 1px solid #fecaca;
  color: #991b1b;
  border-radius: 10px;
  box-shadow: var(--md-shadow-sm);
}

.error-content {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.error-icon {
  font-size: 18px;
  line-height: 1.4;
  flex-shrink: 0;
}

.error-text {
  flex: 1;
  min-width: 0;
}

.error-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.error-hint {
  font-size: 12px;
  color: #991b1b;
  background: rgba(255, 255, 255, 0.55);
  border-radius: 4px;
  padding: 4px 8px;
  margin-bottom: 6px;
  line-height: 1.5;
}

.error-message {
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
  font-family: var(--md-font-mono);
}

.message-bubble {
  max-width: 82%;
  border-radius: 14px;
  padding: 11px 15px;
  word-break: break-word;
  box-shadow: var(--md-shadow-sm);
  transition: box-shadow 0.15s ease;
}
.message-bubble:hover {
  box-shadow: var(--md-shadow-md);
}

.message-bubble.user {
  background: linear-gradient(180deg, #1677ff 0%, #0958d9 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.message-bubble.assistant {
  background: #ffffff;
  color: var(--md-text-primary);
  border: 1px solid var(--md-border-soft);
  border-bottom-left-radius: 4px;
  min-width: 100px;
  box-shadow: var(--md-shadow-sm);
}

.user-content {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.6;
}

/* 编辑态输入框：在气泡内直接替换 user-content */
.edit-input {
  --n-color: rgba(255, 255, 255, 0.15) !important;
}
.edit-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  margin-top: 6px;
}

.edit-btn {
  opacity: 0.4;
  transition: opacity 0.15s;
}
.message-wrapper:hover .edit-btn {
  opacity: 1;
}

.copy-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s, background 0.2s;
  font-size: 12px;
  padding: 1px 5px;
  border-radius: 4px;
  line-height: 1;
}

.message-wrapper:hover .copy-btn,
.copy-btn.copied {
  opacity: 0.7;
}

.copy-btn:hover {
  background: rgba(0, 0, 0, 0.08);
  opacity: 1 !important;
}

@media (hover: none) and (pointer: coarse) {
  .copy-btn { opacity: 0.7; }
}

.user-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.user-files {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 6px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6px;
}

.user-attached-paths {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 6px;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.9);
  align-items: center;
}
.uap-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.75);
  font-weight: 500;
  flex-shrink: 0;
}
.uap-path {
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 11px;
  color: white;
  background: rgba(255, 255, 255, 0.15);
  padding: 1px 6px;
  border-radius: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.file-item {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
  word-break: break-all;
  display: flex;
  align-items: center;
  gap: 6px;
}

.file-icon {
  flex-shrink: 0;
}

.file-name-text {
  flex: 1;
  min-width: 0;
}

.file-size {
  flex-shrink: 0;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.65);
}

.user-image-thumb {
  max-width: 160px;
  max-height: 160px;
  border-radius: 8px;
  cursor: zoom-in;
  border: 1px solid rgba(255,255,255,0.2);
  object-fit: cover;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: zoom-out;
}

.image-preview-full {
  max-width: 92vw;
  max-height: 92vh;
  object-fit: contain;
  border-radius: 6px;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  padding: 0 4px;
}

.message-time {
  font-size: 11px;
  color: #aaa;
}

.token-info {
  font-size: 11px;
  color: #bbb;
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

<style>
.markdown-content {
  font-size: 14px;
  line-height: 1.7;
}

.markdown-content p {
  margin: 0 0 8px;
}

.markdown-content p:last-child {
  margin-bottom: 0;
}

.markdown-content h1, .markdown-content h2, .markdown-content h3 {
  margin: 12px 0 8px;
  font-weight: 600;
}

.markdown-content ul, .markdown-content ol {
  padding-left: 20px;
  margin: 8px 0;
}

.markdown-content code {
  background: #e8e8e8;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  font-size: 12px;
}

.markdown-content .code-block-wrapper {
  position: relative;
  margin: 8px 0;
}

.markdown-content .code-block {
  background: #1e1e1e;
  border-radius: 8px;
  padding: 12px;
  margin: 0;
  overflow-x: auto;
}

.markdown-content .code-copy-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(255, 255, 255, 0.08);
  color: #d4d4d4;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s, background 0.2s;
}

.markdown-content .code-block-wrapper:hover .code-copy-btn {
  opacity: 1;
}

.markdown-content .code-copy-btn:hover {
  background: rgba(255, 255, 255, 0.18);
}

.markdown-content .code-copy-btn.copied {
  background: rgba(82, 196, 26, 0.35);
  border-color: rgba(82, 196, 26, 0.6);
  color: #fff;
}

@media (hover: none) and (pointer: coarse) {
  .markdown-content .code-copy-btn { opacity: 1; }
}

.markdown-content .code-block code {
  background: transparent;
  padding: 0;
  color: #d4d4d4;
  font-size: 13px;
  line-height: 1.5;
}

.markdown-content blockquote {
  border-left: 3px solid #1677ff;
  padding-left: 12px;
  margin: 8px 0;
  color: #666;
}

.markdown-content a {
  color: #1677ff;
  text-decoration: none;
}

.markdown-content a:hover {
  text-decoration: underline;
}

.markdown-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 13px;
}

.markdown-content th, .markdown-content td {
  border: 1px solid #e0e0e0;
  padding: 6px 10px;
}

.markdown-content th {
  background: #f0f0f0;
  font-weight: 600;
}
</style>
