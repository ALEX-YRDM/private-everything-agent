<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallCard from './ToolCallCard.vue'
import { renderMarkdown } from '../utils/markdown'
import { copyToClipboard } from '../utils/clipboard'
import type { DisplayMessage } from '../stores/chat'

const props = defineProps<{ message: DisplayMessage }>()
const msg = useMessage()

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
        <div class="user-content">{{ message.content }}</div>
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
          <span class="error-icon">⚠️</span>
          <div class="error-text">
            <div class="error-title">大模型调用失败</div>
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
  margin-bottom: 16px;
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
  background: #fff2f0;
  border: 1px solid #ffccc7;
  color: #a8071a;
  border-radius: 8px;
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

.error-message {
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
}

.message-bubble {
  max-width: 80%;
  border-radius: 12px;
  padding: 10px 14px;
  word-break: break-word;
}

.message-bubble.user {
  background: #1677ff;
  color: white;
  border-bottom-right-radius: 4px;
}

.message-bubble.assistant {
  background: #f5f5f5;
  color: #1a1a1a;
  border-bottom-left-radius: 4px;
  min-width: 100px;
}

.user-content {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.6;
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
