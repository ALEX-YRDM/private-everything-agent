<script setup lang="ts">
import { computed } from 'vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallCard from './ToolCallCard.vue'
import { renderMarkdown } from '../utils/markdown'
import type { DisplayMessage } from '../stores/chat'

const props = defineProps<{ message: DisplayMessage }>()

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
