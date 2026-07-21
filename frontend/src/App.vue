<script setup lang="ts">
import { ref, computed, onMounted, watch, defineComponent, defineAsyncComponent, provide } from 'vue'
import { NConfigProvider, NMessageProvider, useMessage, darkTheme } from 'naive-ui'
import SessionList from './components/SessionList.vue'
import ChatPanel from './components/ChatPanel.vue'
import FileTreePanel from './components/FileTreePanel.vue'
import CodeViewer from './components/CodeViewer.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import SchedulerPanel from './components/SchedulerPanel.vue'
import TodoPanel from './components/TodoPanel.vue'
// 终端面板依赖 xterm.js（~200KB），按需懒加载；首屏不下载
const TerminalPanel = defineAsyncComponent(() => import('./components/TerminalPanel.vue'))
import { useChatStore } from './stores/chat'
import { useSettingsStore } from './stores/settings'
import { useLayoutStore } from './stores/layout'
import { useThemeStore } from './stores/theme'

const chat = useChatStore()
const settings = useSettingsStore()
const layout = useLayoutStore()
const theme = useThemeStore()
const showScheduler = ref(false)

// Naive UI 主题：dark 走 darkTheme，light 走 null
const naiveTheme = computed(() => theme.effective === 'dark' ? darkTheme : null)

// 当前会话的 working_dir → 决定是否显示右侧文件树
const workingDir = computed(() => chat.currentSession?.working_dir || null)

function handleInsertPath(path: string) {
  chat.requestInsertToInput(path)
}

// 把「打开定时任务 / 打开设置 / 切换终端」通过 provide 暴露给 ChatPanel，
// 让按钮组内嵌到 chat-header 右端，避免 fixed 悬浮与其他 header 元素重叠
provide('openScheduler', () => { showScheduler.value = true })
provide('openSettings', () => { settings.showSettings = true })
provide('toggleTerminal', () => { layout.toggleTerminal() })

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
  <NConfigProvider :theme="naiveTheme">
    <NMessageProvider>
      <TaskNotificationWatcher />
      <div class="app-layout">
        <div class="app-main">
          <!-- 左侧会话列表 -->
          <SessionList />

          <!-- 主聊天区域（含内嵌的顶部按钮组） -->
          <ChatPanel />

          <!-- 代码浏览器（只读，中部悬浮） -->
          <CodeViewer />

          <!-- 本地终端抽屉（多 tab）——只在首次打开时懒加载 xterm chunk -->
          <TerminalPanel v-if="layout.terminalOpen" />

          <!-- 右侧文件树（会话存在即显示；未绑定 working_dir 时展示默认 workspace） -->
          <FileTreePanel
            v-if="chat.currentSessionId"
            :session-id="chat.currentSessionId"
            :working-dir="workingDir"
            @insert-path="handleInsertPath"
          />
        </div>

        <!-- 设置面板 -->
        <SettingsPanel />

        <!-- 定时任务面板 -->
        <SchedulerPanel v-model:show="showScheduler" />

        <!-- Todo 悬浮面板：Agent 通过 todo_write 维护，用户可切换/编辑 -->
        <TodoPanel />
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
  font-family: var(--md-font-sans);
}

.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.app-main {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}
</style>
