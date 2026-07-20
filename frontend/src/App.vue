<script setup lang="ts">
import { ref, computed, onMounted, watch, defineComponent } from 'vue'
import { NConfigProvider, NMessageProvider, NButton, NTooltip, NSpace, useMessage } from 'naive-ui'
import SessionList from './components/SessionList.vue'
import ChatPanel from './components/ChatPanel.vue'
import FileTreePanel from './components/FileTreePanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import SchedulerPanel from './components/SchedulerPanel.vue'
import { useChatStore } from './stores/chat'
import { useSettingsStore } from './stores/settings'

const chat = useChatStore()
const settings = useSettingsStore()
const showScheduler = ref(false)

// 当前会话的 working_dir → 决定是否显示右侧文件树
const workingDir = computed(() => chat.currentSession?.working_dir || null)

function handleInsertPath(path: string) {
  // 简单实现：TODO 后续可接入 ChatPanel 输入框
  navigator.clipboard?.writeText(path).catch(() => {})
}

onMounted(async () => {
  await settings.init()
  await chat.init()
})

const TaskNotificationWatcher = defineComponent({
  setup() {
    const msg = useMessage()
    watch(() => chat.lastTaskNotification, (n) => {
      if (!n) return
      if (n.status === 'success') {
        msg.success(n.message, { duration: 5000 })
      } else {
        msg.error(n.message, { duration: 8000 })
      }
    })
    watch(() => chat.lastError, (e) => {
      if (!e) return
      msg.error(`大模型调用失败：${e.message}`, { duration: 8000 })
    })
    return () => null
  },
})
</script>

<template>
  <NConfigProvider>
    <NMessageProvider>
      <TaskNotificationWatcher />
      <div class="app-layout">
        <!-- 左侧会话列表 -->
        <SessionList />

        <!-- 主聊天区域 -->
        <ChatPanel />

        <!-- 右侧文件树（仅当会话绑定 working_dir 时） -->
        <FileTreePanel
          v-if="workingDir"
          :session-id="chat.currentSessionId"
          :working-dir="workingDir"
          @insert-path="handleInsertPath"
        />

        <!-- 右上角操作按钮组 -->
        <div class="top-actions">
          <NSpace>
            <NTooltip>
              <template #trigger>
                <NButton circle @click="showScheduler = true">⏰</NButton>
              </template>
              定时任务
            </NTooltip>
            <NTooltip>
              <template #trigger>
                <NButton circle @click="settings.showSettings = true">⚙️</NButton>
              </template>
              系统设置
            </NTooltip>
          </NSpace>
        </div>

        <!-- 设置面板 -->
        <SettingsPanel />

        <!-- 定时任务面板 -->
        <SchedulerPanel v-model:show="showScheduler" />
      </div>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
*, *::before, *::after {
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', sans-serif;
}

.app-layout {
  height: 100vh;
  display: flex;
  position: relative;
  overflow: hidden;
}

.top-actions {
  position: fixed;
  top: 10px;
  right: 14px;
  z-index: 100;
}
</style>
