<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { NInput, NButton, NScrollbar, NSpin, NEmpty, NTooltip } from 'naive-ui'
import MessageBubble from './MessageBubble.vue'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
const inputText = ref('')
const scrollbarRef = ref<InstanceType<typeof NScrollbar> | null>(null)

const allMessages = computed(() => {
  const msgs = [...chat.messages]
  if (chat.streamingMessage) {
    msgs.push(chat.streamingMessage)
  }
  return msgs
})

function scrollToBottom() {
  nextTick(() => {
    scrollbarRef.value?.scrollTo({ top: 999999, behavior: 'smooth' })
  })
}

watch(allMessages, scrollToBottom, { deep: true })

async function sendMessage() {
  const content = inputText.value.trim()
  if (!content || chat.isStreaming) return
  inputText.value = ''
  await chat.sendMessage(content)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="chat-panel">
    <!-- 顶部标题栏 -->
    <div class="chat-header">
      <span class="chat-title">
        {{ chat.currentSession?.title || '选择或创建会话' }}
      </span>
    </div>

    <!-- 消息区域 -->
    <NScrollbar ref="scrollbarRef" class="messages-area">
      <div class="messages-container">
        <NEmpty
          v-if="allMessages.length === 0 && !chat.isStreaming"
          description="发送消息开始对话"
          class="empty-chat"
        />
        <MessageBubble
          v-for="msg in allMessages"
          :key="msg.id"
          :message="msg"
        />
        <div v-if="chat.isStreaming && !chat.streamingMessage" class="typing-indicator">
          <NSpin size="small" />
          <span>思考中…</span>
        </div>
      </div>
    </NScrollbar>

    <!-- 输入区域 -->
    <div class="input-area" v-if="chat.currentSessionId">
      <NInput
        v-model:value="inputText"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 6 }"
        :placeholder="chat.isStreaming ? '等待响应完成…' : '发送消息（Enter 发送，Shift+Enter 换行）'"
        :disabled="chat.isStreaming"
        @keydown="handleKeydown"
        class="message-input"
      />
      <div class="input-actions">
        <NTooltip v-if="chat.isStreaming">
          <template #trigger>
            <NButton
              type="error"
              size="medium"
              @click="chat.stopStreaming()"
            >
              停止
            </NButton>
          </template>
          停止当前响应
        </NTooltip>
        <NButton
          v-else
          type="primary"
          size="medium"
          :disabled="!inputText.trim()"
          @click="sendMessage"
        >
          发送
        </NButton>
      </div>
    </div>
    <div v-else class="no-session-hint">
      请从左侧选择或创建一个会话
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: white;
}

.chat-header {
  padding: 14px 20px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  min-height: 52px;
}

.chat-title {
  font-weight: 600;
  font-size: 15px;
  color: #1a1a1a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.messages-area {
  flex: 1;
}

.messages-container {
  padding: 16px 20px;
  min-height: 100%;
}

.empty-chat {
  margin-top: 60px;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  color: #888;
  font-size: 13px;
}

.input-area {
  border-top: 1px solid #e8e8e8;
  padding: 12px 16px;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.message-input {
  flex: 1;
}

.input-actions {
  flex-shrink: 0;
}

.no-session-hint {
  border-top: 1px solid #e8e8e8;
  padding: 16px;
  text-align: center;
  color: #aaa;
  font-size: 13px;
}
</style>
