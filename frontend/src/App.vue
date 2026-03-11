<script setup lang="ts">
import { onMounted } from 'vue'
import { NConfigProvider, NMessageProvider, NButton, NTooltip } from 'naive-ui'
import SessionList from './components/SessionList.vue'
import ChatPanel from './components/ChatPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import { useChatStore } from './stores/chat'
import { useSettingsStore } from './stores/settings'

const chat = useChatStore()
const settings = useSettingsStore()

onMounted(async () => {
  await settings.init()
  await chat.init()
})
</script>

<template>
  <NConfigProvider>
    <NMessageProvider>
      <div class="app-layout">
        <!-- 左侧会话列表 -->
        <SessionList />

        <!-- 主聊天区域 -->
        <ChatPanel />

        <!-- 右上角设置按钮 -->
        <div class="settings-trigger">
          <NTooltip>
            <template #trigger>
              <NButton circle @click="settings.showSettings = true">
                ⚙️
              </NButton>
            </template>
            设置
          </NTooltip>
        </div>

        <!-- 设置面板（Drawer） -->
        <SettingsPanel />
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

.settings-trigger {
  position: fixed;
  top: 12px;
  right: 16px;
  z-index: 100;
}
</style>
