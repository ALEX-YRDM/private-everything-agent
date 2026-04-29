<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NTag, NSwitch, NTooltip, useMessage } from 'naive-ui'
import { api, type ToolState } from '../../api/http'

const message = useMessage()
const globalToolStates = ref<ToolState[]>([])
const togglingTool = ref<string | null>(null)

async function loadGlobalToolStates() {
  try { globalToolStates.value = (await api.toolState.getAll()).tools } catch (e) { console.error(e) }
}

async function toggleGlobal(toolName: string) {
  togglingTool.value = toolName
  try {
    const res = await api.toolState.toggleGlobal(toolName)
    const t = globalToolStates.value.find(x => x.name === toolName)
    if (t) t.global_enabled = res.globally_enabled
    message.success(`工具「${toolName}」全局${res.globally_enabled ? '已启用' : '已禁用'}`)
  } catch (e) { message.error(String(e)) } finally { togglingTool.value = null }
}

onMounted(loadGlobalToolStates)
</script>

<template>
  <div class="section">
    <h4>全局工具开关</h4>
    <p class="hint">全局禁用后，该工具在所有会话中默认不可用。可在聊天界面的「🔧 工具」面板中为单个会话设置覆盖。</p>
    <div v-for="tool in globalToolStates" :key="tool.name" class="global-tool-row">
      <div class="global-tool-info">
        <code class="tool-code">{{ tool.name }}</code>
        <NTag size="tiny" :type="tool.global_enabled ? 'success' : 'default'">{{ tool.global_enabled ? '全局启用' : '全局禁用' }}</NTag>
      </div>
      <NTooltip>
        <template #trigger>
          <NSwitch :value="tool.global_enabled" :loading="togglingTool === tool.name" @update:value="toggleGlobal(tool.name)" />
        </template>
        {{ tool.global_enabled ? '点击全局禁用' : '点击全局启用' }}
      </NTooltip>
    </div>
  </div>
</template>

<style scoped>
@import './settings-common.css';
</style>