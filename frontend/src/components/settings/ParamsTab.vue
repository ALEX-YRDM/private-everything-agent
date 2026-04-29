<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NForm, NFormItem, NInputNumber, NAlert, NSpace, NButton, useMessage } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'

const settings = useSettingsStore()
const message = useMessage()

const llmParamsForm = ref({ max_tokens: 4096, temperature: 0.1, context_window_tokens: 65536, max_iterations: 40 })
const savingLlmParams = ref(false)

async function saveLlmParams() {
  savingLlmParams.value = true
  try {
    await settings.updateLlmParams({ ...llmParamsForm.value })
    message.success('参数已保存并立即生效')
  } catch (e) { message.error(`保存失败: ${String(e)}`) }
  finally { savingLlmParams.value = false }
}

onMounted(() => { llmParamsForm.value = { ...settings.llmParams } })
</script>

<template>
  <div class="section">
    <h4>LLM 运行参数</h4>
    <NAlert type="info" :show-icon="false" class="scope-tip">修改后点击保存，立即全局生效，重启后保持。</NAlert>
    <NForm label-placement="left" label-width="130" style="margin-top:12px">
      <NFormItem label="最大输出 Tokens">
        <NInputNumber v-model:value="llmParamsForm.max_tokens" :min="256" :max="200000" :step="256" style="width:180px" />
        <template #feedback>
          <span style="font-size:11px;color:#999">每次回复最多生成的 token 数（建议 4096–32768）</span>
        </template>
      </NFormItem>
      <NFormItem label="温度 Temperature">
        <NInputNumber v-model:value="llmParamsForm.temperature" :min="0" :max="2" :step="0.1" :precision="1" style="width:180px" />
        <template #feedback>
          <span style="font-size:11px;color:#999">0 = 确定性，0.1–0.7 = 平衡，≥1 = 创意</span>
        </template>
      </NFormItem>
      <NFormItem label="上下文窗口">
        <NInputNumber v-model:value="llmParamsForm.context_window_tokens" :min="4096" :max="2000000" :step="4096" style="width:180px" />
        <template #feedback>
          <span style="font-size:11px;color:#999">模型最大上下文长度，用于触发自动记忆整合（超过 80%）</span>
        </template>
      </NFormItem>
      <NFormItem label="最大迭代次数">
        <NInputNumber v-model:value="llmParamsForm.max_iterations" :min="1" :max="200" :step="1" style="width:180px" />
        <template #feedback>
          <span style="font-size:11px;color:#999">每次回复 Agent 最多调用工具的轮次</span>
        </template>
      </NFormItem>
    </NForm>
    <NSpace justify="end" style="margin-top:8px">
      <NButton type="primary" :loading="savingLlmParams" @click="saveLlmParams">保存参数</NButton>
    </NSpace>
  </div>
</template>

<style scoped>
@import './settings-common.css';
</style>