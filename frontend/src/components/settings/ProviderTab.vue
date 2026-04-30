<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  NButton, NSpace, NPopconfirm, NTag, NCollapse, NCollapseItem,
  NEmpty, NBadge, NTooltip, NSpin, NModal, NForm, NFormItem,
  NInput, NInputNumber, NSwitch, NAlert, useMessage,
} from 'naive-ui'
import { useSettingsStore, type ProviderKey } from '../../stores/settings'
import { api, type ProviderModel } from '../../api/http'

const settings = useSettingsStore()
const message = useMessage()

const STANDARD_PROVIDERS = new Set([
  "openai","anthropic","gemini","deepseek","groq","mistral","together_ai","openrouter","xai","perplexity","cohere",
  "azure","bedrock","vertex_ai",
  "volcengine","moonshot","zhipuai","zai","baidu","dashscope","minimax","qianfan","spark","hunyuan",
  "ollama","palm","replicate","huggingface",
  "ai21","nlp_cloud","aleph_alpha","petals","anyscale","voyage","openllm","oobabooga",
])

// Provider 编辑
const showProviderModal = ref(false)
const isNewProvider = ref(false)
const providerForm = ref({ provider: '', display_name: '', api_key: '', api_base: '' })
const savingProvider = ref(false)
const isCustomProvider = computed(() => !!providerForm.value.provider && !STANDARD_PROVIDERS.has(providerForm.value.provider.toLowerCase()))
const providerIdFeedback = computed(() => {
  if (!providerForm.value.provider) return ''
  return isCustomProvider.value
    ? '⚠️ 非标准 Provider，LiteLLM 无内置路由 — 必须填写 API Base URL'
    : `✓ 标准 Provider，LiteLLM 自动路由，模型 ID 格式：${providerForm.value.provider}/模型名`
})

function openAddProvider() {
  isNewProvider.value = true
  providerForm.value = { provider: '', display_name: '', api_key: '', api_base: '' }
  showProviderModal.value = true
}
function openEditProvider(pk: ProviderKey) {
  isNewProvider.value = false
  providerForm.value = { provider: pk.provider, display_name: pk.display_name, api_key: '', api_base: pk.api_base || '' }
  showProviderModal.value = true
}
async function saveProvider() {
  if (!providerForm.value.provider.trim() || !providerForm.value.display_name.trim()) { message.warning('请填写 Provider ID 和显示名称'); return }
  if (isCustomProvider.value && !providerForm.value.api_base.trim()) { message.warning('自定义 Provider 必须填写 API Base URL'); return }
  savingProvider.value = true
  try {
    await api.providerKeys.upsert({ provider: providerForm.value.provider.trim(), display_name: providerForm.value.display_name.trim(), api_key: providerForm.value.api_key || null, api_base: providerForm.value.api_base || null })
    showProviderModal.value = false
    await settings.loadProviders()
    message.success(`Provider「${providerForm.value.provider}」已保存`)
  } catch (e) { message.error(String(e)) } finally { savingProvider.value = false }
}
async function deleteProvider(provider: string) {
  try { await api.providerKeys.delete(provider); await settings.loadProviders(); message.success('已删除') } catch (e) { message.error(String(e)) }
}

// 模型管理
const showModelModal = ref(false)
const editingModelProvider = ref('')
const editingModelIndex = ref<number | null>(null)
const modelForm = ref({
  id: '',
  label: '',
  supports_vision: true,
  context_window_tokens: null as number | null,
  max_tokens: null as number | null,
})
const testingModel = ref('')
const testResults = ref<Record<string, 'ok' | 'fail' | 'testing'>>({})

function openAddModel(provider: string) {
  editingModelProvider.value = provider
  editingModelIndex.value = null
  modelForm.value = { id: '', label: '', supports_vision: true, context_window_tokens: null, max_tokens: null }
  showModelModal.value = true
}
function openEditModel(provider: string, index: number, model: ProviderModel) {
  editingModelProvider.value = provider
  editingModelIndex.value = index
  modelForm.value = {
    id: model.id,
    label: model.label,
    supports_vision: model.supports_vision !== false,
    context_window_tokens: model.context_window_tokens ?? null,
    max_tokens: model.max_tokens ?? null,
  }
  showModelModal.value = true
}
async function saveModel() {
  if (!modelForm.value.id.trim() || !modelForm.value.label.trim()) { message.warning('请填写模型 ID 和显示名称'); return }
  const pk = settings.providerGroups.find(p => p.provider === editingModelProvider.value)
  if (!pk) return
  const models = [...pk.models]
  const newModel: ProviderModel = {
    id: modelForm.value.id.trim(),
    label: modelForm.value.label.trim(),
    supports_vision: modelForm.value.supports_vision,
    context_window_tokens: modelForm.value.context_window_tokens ?? undefined,
    max_tokens: modelForm.value.max_tokens ?? undefined,
  }
  if (editingModelIndex.value === null) models.push(newModel); else models[editingModelIndex.value] = newModel
  try { await api.providerKeys.updateModels(editingModelProvider.value, models); showModelModal.value = false; await settings.loadProviders(); message.success('模型已保存') } catch (e) { message.error(String(e)) }
}
async function deleteModel(provider: string, index: number) {
  const pk = settings.providerGroups.find(p => p.provider === provider)
  if (!pk) return
  try { await api.providerKeys.updateModels(provider, pk.models.filter((_, i) => i !== index)); await settings.loadProviders(); message.success('已删除') } catch (e) { message.error(String(e)) }
}
async function testModel(modelId: string) {
  testResults.value[modelId] = 'testing'; testingModel.value = modelId
  try {
    const res = await api.models.test(modelId)
    testResults.value[modelId] = res.ok ? 'ok' : 'fail'
    res.ok ? message.success(`模型 ${modelId} 调用正常 ✓`) : message.error(`调用失败: ${res.error || '未知错误'}`)
  } catch (e) { testResults.value[modelId] = 'fail'; message.error(`调用失败: ${String(e)}`) } finally { testingModel.value = '' }
}
function autoFillModelId() { if (!modelForm.value.id && editingModelProvider.value) modelForm.value.id = editingModelProvider.value + '/' }
</script>

<template>
  <div class="section">
    <div class="section-header">
      <div>
        <h4 style="margin:0">服务商 & 模型管理</h4>
        <p class="hint" style="margin:4px 0 0">每个服务商配置一次 API Key，下挂多个模型；模型列表可自由增删。</p>
      </div>
      <NButton size="small" type="primary" @click="openAddProvider">+ 新增服务商</NButton>
    </div>
  </div>

  <NEmpty v-if="settings.providerGroups.length === 0" description="暂无服务商配置，点击「新增服务商」添加" style="margin: 24px 0" />
  <NCollapse v-else display-directive="show">
    <NCollapseItem v-for="pk in settings.providerGroups" :key="pk.provider" :name="pk.provider">
      <template #header>
        <div class="provider-header">
          <span class="provider-name">{{ pk.display_name }}</span>
          <code class="provider-id">{{ pk.provider }}</code>
          <NTag v-if="pk.api_key" type="success" size="small">Key ✓</NTag>
          <NTag v-else type="default" size="small">无 Key</NTag>
          <NTag v-if="pk.api_base" size="small" type="info">自定义地址</NTag>
          <NBadge :value="pk.models.length" :max="99" type="info" style="margin-left:4px"><span style="font-size:11px;color:#999">个模型</span></NBadge>
        </div>
      </template>
      <template #header-extra>
        <NSpace size="small" @click.stop>
          <NButton size="tiny" @click.stop="openEditProvider(pk)">编辑 Key</NButton>
          <NPopconfirm @positive-click="deleteProvider(pk.provider)">
            <template #trigger><NButton size="tiny" type="error" ghost @click.stop>删除</NButton></template>
            确定删除服务商「{{ pk.display_name }}」及其所有模型？
          </NPopconfirm>
        </NSpace>
      </template>
      <div class="models-section">
        <div class="models-header">
          <span class="models-title">模型列表（{{ pk.models.length }}）</span>
          <NButton size="tiny" type="primary" ghost @click="openAddModel(pk.provider)">+ 添加模型</NButton>
        </div>
        <NEmpty v-if="pk.models.length === 0" description="暂无模型，点击添加" :style="{ margin: '12px 0' }" />
        <div v-for="(model, idx) in pk.models" :key="model.id" class="model-row">
          <div class="model-info">
            <span class="model-label">{{ model.label }}</span>
            <code class="model-id-text">{{ model.id }}</code>
            <NTag v-if="model.supports_vision !== false" size="tiny" type="info">视觉</NTag>
            <NTag v-if="model.context_window_tokens" size="tiny">{{ (model.context_window_tokens / 1000).toFixed(0) }}K 上下文</NTag>
          </div>
          <div class="model-actions">
            <NTag v-if="testResults[model.id] === 'ok'" type="success" size="tiny">✓ 可用</NTag>
            <NTag v-else-if="testResults[model.id] === 'fail'" type="error" size="tiny">✗ 失败</NTag>
            <NSpin v-else-if="testResults[model.id] === 'testing'" size="small" />
            <NTooltip><template #trigger><NButton size="tiny" :loading="testingModel === model.id" @click="testModel(model.id)">测试</NButton></template>发送一条最小请求校验模型是否可正常调用</NTooltip>
            <NButton size="tiny" @click="openEditModel(pk.provider, idx, model)">编辑</NButton>
            <NPopconfirm @positive-click="deleteModel(pk.provider, idx)"><template #trigger><NButton size="tiny" type="error" ghost>删除</NButton></template>确定删除模型「{{ model.label }}」？</NPopconfirm>
          </div>
        </div>
      </div>
    </NCollapseItem>
  </NCollapse>

  <!-- 服务商 Modal -->
  <NModal v-model:show="showProviderModal" preset="card" :title="isNewProvider ? '新增服务商' : '编辑服务商'" :style="{ width: '500px' }">
    <NAlert type="info" :show-icon="true" style="margin-bottom:14px;font-size:12px" title="接入 OpenAI 兼容的自定义服务">
      <div>将 <b>Provider ID</b> 设为 <code>openai</code>，在 <b>API Base URL</b> 填入你的服务地址（需包含 <code>/v1</code>）。</div>
    </NAlert>
    <NForm label-placement="left" label-width="110">
      <NFormItem label="Provider ID" :feedback="providerIdFeedback" :validation-status="isCustomProvider ? 'warning' : undefined">
        <NInput v-model:value="providerForm.provider" :disabled="!isNewProvider" placeholder="如：openai / deepseek / my_service" />
      </NFormItem>
      <NFormItem label="显示名称"><NInput v-model:value="providerForm.display_name" placeholder="如：OpenAI / 我的本地模型" /></NFormItem>
      <NFormItem label="API Key"><NInput v-model:value="providerForm.api_key" type="password" show-password-on="click" placeholder="留空则不修改已保存的 Key" /></NFormItem>
      <NFormItem label="API Base URL"
        :feedback="isCustomProvider && !providerForm.api_base ? '⚠️ 自定义 Provider 必须填写服务地址' : ''"
        :validation-status="isCustomProvider && !providerForm.api_base ? 'error' : undefined">
        <NInput v-model:value="providerForm.api_base" :placeholder="isCustomProvider ? '必填：http://your-server/v1' : '可选，如 Ollama: http://localhost:11434'" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showProviderModal = false">取消</NButton>
        <NButton type="primary" :loading="savingProvider" @click="saveProvider">保存</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- 模型 Modal -->
  <NModal v-model:show="showModelModal" preset="card" :title="editingModelIndex === null ? `为 ${editingModelProvider} 添加模型` : '编辑模型'" :style="{ width: '480px' }">
    <NForm label-placement="left" label-width="100">
      <NFormItem label="模型 ID">
        <NInput v-model:value="modelForm.id" placeholder="如：openai/gpt-4o" @focus="autoFillModelId" />
        <template #feedback><span style="font-size:11px;color:#999">格式：{provider}/{model_name}，参考 LiteLLM 文档</span></template>
      </NFormItem>
      <NFormItem label="显示名称"><NInput v-model:value="modelForm.label" placeholder="如：GPT-4o" /></NFormItem>
      <NFormItem label="支持视觉">
        <NSwitch v-model:value="modelForm.supports_vision" />
        <template #feedback><span style="font-size:11px;color:#999">关闭后此模型不显示图片上传按钮</span></template>
      </NFormItem>
      <NFormItem label="上下文窗口">
        <NInputNumber
          v-model:value="modelForm.context_window_tokens"
          :min="1024" :max="10000000" :step="4096"
          placeholder="如：128000（覆盖全局设置）"
          clearable
          style="width:100%"
        />
        <template #feedback><span style="font-size:11px;color:#999">该模型最大输入 token 数，留空则使用全局配置</span></template>
      </NFormItem>
      <NFormItem label="最大输出 Tokens">
        <NInputNumber
          v-model:value="modelForm.max_tokens"
          :min="1024" :max="1000000" :step="256"
          placeholder="如：8192（覆盖全局设置）"
          clearable
          style="width:100%"
        />
        <template #feedback><span style="font-size:11px;color:#999">该模型每次回复最多生成的 token 数，留空则使用全局配置</span></template>
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showModelModal = false">取消</NButton>
        <NButton type="primary" @click="saveModel">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
@import './settings-common.css';
</style>