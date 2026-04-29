<script setup lang="ts">
import { NSelect, NAlert, useMessage } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'

const settings = useSettingsStore()
const message = useMessage()

async function switchModel(modelId: string) {
  try {
    await settings.setModel(modelId)
    message.success(`已切换到 ${modelId}（全局生效）`)
  } catch { message.error('模型切换失败') }
}
</script>

<template>
  <div class="section">
    <h4>当前模型（全局切换）</h4>
    <NAlert type="info" :show-icon="false" class="scope-tip">
      切换后立即全局生效：所有对话和定时任务（无单独指定模型时）都使用此模型。
    </NAlert>
    <NSelect
      :value="settings.currentModel"
      :options="settings.modelSelectOptions"
      filterable tag
      placeholder="选择或输入模型 ID"
      class="model-select"
      @update:value="switchModel"
    />
    <p class="hint">
      当前: <code>{{ settings.currentModel }}</code>
      &nbsp;·&nbsp;
      <span style="color:#999">在「🔑 服务商」标签页中管理 API Key 和模型列表</span>
    </p>
  </div>
</template>

<style scoped>
@import './settings-common.css';
</style>