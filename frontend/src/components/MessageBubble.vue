<script setup lang="ts">
import { ref, computed } from 'vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallCard from './ToolCallCard.vue'
import { renderMarkdown } from '../utils/markdown'
import type { DisplayMessage } from '../stores/chat'

const props = defineProps<{ message: DisplayMessage }>()

const previewImage = ref<string | null>(null)

const formattedTime = computed(() => {
  return new Date(props.message.timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
})

const renderedContent = computed(() => renderMarkdown(props.message.content))
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
        />
        <span v-if="message.isStreaming" class="cursor-blink">▋</span>
      </template>
    </div>
    <div class="message-time">{{ formattedTime }}</div>
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

.user-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
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

.message-time {
  font-size: 11px;
  color: #aaa;
  margin-top: 4px;
  padding: 0 4px;
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

.markdown-content .code-block {
  background: #1e1e1e;
  border-radius: 8px;
  padding: 12px;
  margin: 8px 0;
  overflow-x: auto;
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
