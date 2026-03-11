<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NDrawer, NDrawerContent, NSelect, NDivider, NTag, NButton,
  NModal, NForm, NFormItem, NInput, NInputNumber,
  NDataTable, useMessage, NTabs, NTabPane, NSpace, NPopconfirm,
  NAlert, NSwitch, NTooltip,
} from 'naive-ui'
import { useSettingsStore, buildModelSelectOptions } from '../stores/settings'
import { api, type ModelConfig, type ProviderKey, type PromptTemplate, type ToolState } from '../api/http'

const settings = useSettingsStore()
const message = useMessage()

// ── 模型快速切换 ─────────────────────────────────────────────────────────────
const modelOptions = buildModelSelectOptions()

async function switchModel(modelId: string) {
  try {
    await settings.setModel(modelId)
    message.success(`已切换到 ${modelId}（全局生效）`)
  } catch {
    message.error('模型切换失败')
  }
}

// ── 模型预设配置 ─────────────────────────────────────────────────────────────
const modelConfigs = ref<ModelConfig[]>([])
const showConfigModal = ref(false)
const editingConfig = ref<ModelConfig | null>(null)
const configForm = ref({ name: '', model_id: '', temperature: 0.1, max_tokens: 4096 })

async function loadModelConfigs() {
  try {
    const data = await api.modelConfigs.list()
    modelConfigs.value = data.configs
  } catch (e) { console.error(e) }
}

function openCreateConfig() {
  editingConfig.value = null
  configForm.value = { name: '', model_id: settings.currentModel, temperature: 0.1, max_tokens: 4096 }
  showConfigModal.value = true
}

function openEditConfig(cfg: ModelConfig) {
  editingConfig.value = cfg
  configForm.value = { name: cfg.name, model_id: cfg.model_id, temperature: cfg.temperature, max_tokens: cfg.max_tokens }
  showConfigModal.value = true
}

async function saveConfig() {
  if (!configForm.value.name.trim() || !configForm.value.model_id.trim()) {
    message.warning('请填写名称和模型 ID')
    return
  }
  try {
    if (editingConfig.value) {
      await api.modelConfigs.update(editingConfig.value.id, configForm.value)
      message.success('预设已更新')
    } else {
      await api.modelConfigs.create(configForm.value)
      message.success('预设已保存')
    }
    showConfigModal.value = false
    await loadModelConfigs()
  } catch (e) { message.error(String(e)) }
}

async function activateConfig(cfg: ModelConfig) {
  try {
    await api.modelConfigs.activate(cfg.id)
    settings.currentModel = cfg.model_id
    message.success(`已激活预设「${cfg.name}」，模型: ${cfg.model_id}`)
    await loadModelConfigs()
  } catch (e) { message.error(String(e)) }
}

async function deleteConfig(cfg: ModelConfig) {
  try {
    await api.modelConfigs.delete(cfg.id)
    await loadModelConfigs()
    message.success('已删除')
  } catch (e) { message.error(String(e)) }
}

const configColumns = [
  { title: '名称', key: 'name' },
  { title: '模型 ID', key: 'model_id', ellipsis: { tooltip: true } },
  { title: '默认', key: 'is_default', width: 60,
    render: (row: ModelConfig) => row.is_default ? h(NTag, { type: 'success', size: 'small' }, { default: () => '✓' }) : '' },
  { title: '操作', key: 'actions', width: 160,
    render: (row: ModelConfig) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => activateConfig(row) }, { default: () => '激活' }),
        h(NButton, { size: 'tiny', onClick: () => openEditConfig(row) }, { default: () => '编辑' }),
        h(NPopconfirm, { onPositiveClick: () => deleteConfig(row) }, {
          trigger: () => h(NButton, { size: 'tiny', type: 'error', ghost: true }, { default: () => '删除' }),
          default: () => '确定删除此预设？',
        }),
      ],
    }),
  },
]

// ── Provider API Keys ────────────────────────────────────────────────────────

// 预定义的服务商列表
const PROVIDERS = [
  { value: 'openai',       label: 'OpenAI',             placeholder: 'sk-...' },
  { value: 'anthropic',    label: 'Anthropic',           placeholder: 'sk-ant-...' },
  { value: 'gemini',       label: 'Google Gemini',       placeholder: 'AIza...' },
  { value: 'deepseek',     label: 'DeepSeek',            placeholder: 'sk-...' },
  { value: 'xai',          label: 'xAI (Grok)',          placeholder: 'xai-...' },
  { value: 'groq',         label: 'Groq',                placeholder: 'gsk_...' },
  { value: 'mistral',      label: 'Mistral AI',          placeholder: 'your-key' },
  { value: 'together_ai',  label: 'Together AI',         placeholder: 'your-key' },
  { value: 'openrouter',   label: 'OpenRouter',          placeholder: 'sk-or-...' },
  { value: 'perplexity',   label: 'Perplexity',          placeholder: 'pplx-...' },
  { value: 'volcengine',   label: '字节跳动 (火山引擎)',  placeholder: 'your-key' },
  { value: 'moonshot',     label: '月之暗面 (Kimi)',     placeholder: 'your-key' },
  { value: 'ollama',       label: 'Ollama (本地)',       placeholder: '无需 Key' },
]

const providerKeys = ref<ProviderKey[]>([])
const showKeyModal = ref(false)
const keyForm = ref({ provider: '', display_name: '', api_key: '', api_base: '' })
async function loadProviderKeys() {
  try {
    const data = await api.providerKeys.list()
    providerKeys.value = data.keys
  } catch (e) { console.error(e) }
}

function openAddKey(provider?: string) {
  const p = PROVIDERS.find(x => x.value === provider)
  keyForm.value = {
    provider: provider || '',
    display_name: p?.label || '',
    api_key: '',
    api_base: '',
  }
  showKeyModal.value = true
}

function openEditKey(key: ProviderKey) {
  keyForm.value = {
    provider: key.provider,
    display_name: key.display_name,
    api_key: '',  // 不回填密钥，留空=不修改
    api_base: key.api_base || '',
  }
  showKeyModal.value = true
}

async function saveKey() {
  if (!keyForm.value.provider.trim()) {
    message.warning('请选择或输入 Provider 名称')
    return
  }
  try {
    const p = PROVIDERS.find(x => x.value === keyForm.value.provider)
    await api.providerKeys.upsert({
      provider: keyForm.value.provider,
      display_name: keyForm.value.display_name || p?.label || keyForm.value.provider,
      api_key: keyForm.value.api_key || undefined,
      api_base: keyForm.value.api_base || undefined,
    })
    showKeyModal.value = false
    await loadProviderKeys()
    message.success(`Provider「${keyForm.value.provider}」密钥已保存`)
  } catch (e) { message.error(String(e)) }
}

async function deleteKey(provider: string) {
  try {
    await api.providerKeys.delete(provider)
    await loadProviderKeys()
    message.success('已删除')
  } catch (e) { message.error(String(e)) }
}

function getKeyStatus(provider: string) {
  return providerKeys.value.find(k => k.provider === provider)
}


// ── 提示词模板管理 ───────────────────────────────────────────────────────────
const templates = ref<PromptTemplate[]>([])
const showTplModal = ref(false)
const editingTpl = ref<PromptTemplate | null>(null)
const tplForm = ref({ name: '', content: '', category: '通用', sort_order: 0 })

const CATEGORIES = ['通用', '编程', '研究', '写作', '翻译', '效率', '其他']

async function loadTemplates() {
  try {
    const data = await api.templates.list()
    templates.value = data.templates
  } catch (e) { console.error(e) }
}

function openCreateTpl() {
  editingTpl.value = null
  tplForm.value = { name: '', content: '', category: '通用', sort_order: 0 }
  showTplModal.value = true
}

function openEditTpl(tpl: PromptTemplate) {
  editingTpl.value = tpl
  tplForm.value = { name: tpl.name, content: tpl.content, category: tpl.category, sort_order: tpl.sort_order }
  showTplModal.value = true
}

async function saveTpl() {
  if (!tplForm.value.name.trim() || !tplForm.value.content.trim()) {
    message.warning('请填写模板名称和内容')
    return
  }
  try {
    if (editingTpl.value) {
      await api.templates.update(editingTpl.value.id, tplForm.value)
      message.success('模板已更新')
    } else {
      await api.templates.create(tplForm.value)
      message.success('模板已创建')
    }
    showTplModal.value = false
    await loadTemplates()
  } catch (e) { message.error(String(e)) }
}

async function deleteTpl(tpl: PromptTemplate) {
  try {
    await api.templates.delete(tpl.id)
    await loadTemplates()
    message.success('已删除')
  } catch (e) { message.error(String(e)) }
}

// 模板列表列配置
const tplColumns = [
  { title: '名称', key: 'name', width: 120 },
  { title: '分类', key: 'category', width: 70 },
  { title: '内容预览', key: 'content',
    render: (row: PromptTemplate) => h('span', { style: 'color:#888;font-size:12px' },
      row.content.slice(0, 30) + (row.content.length > 30 ? '…' : ''))
  },
  { title: '操作', key: 'actions', width: 110,
    render: (row: PromptTemplate) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { size: 'tiny', onClick: () => openEditTpl(row) }, { default: () => '编辑' }),
        h(NPopconfirm, { onPositiveClick: () => deleteTpl(row) }, {
          trigger: () => h(NButton, { size: 'tiny', type: 'error', ghost: true }, { default: () => '删除' }),
          default: () => '确定删除此模板？',
        }),
      ],
    }),
  },
]

// ── 全局工具管理 ─────────────────────────────────────────────────────────────
const globalToolStates = ref<ToolState[]>([])
const togglingTool = ref<string | null>(null)

async function loadGlobalToolStates() {
  try {
    const data = await api.toolState.getAll()
    globalToolStates.value = data.tools
  } catch (e) { console.error(e) }
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

onMounted(async () => {
  await settings.init()
  await Promise.all([loadModelConfigs(), loadProviderKeys(), loadTemplates(), loadGlobalToolStates()])
})
</script>

<template>
  <NDrawer
    :show="settings.showSettings"
    @update:show="settings.showSettings = $event"
    :width="560"
    placement="right"
  >
    <NDrawerContent :native-scrollbar="false" title="系统设置">
      <NTabs type="line" animated>

        <!-- Tab 1: 模型 -->
        <NTabPane name="model" tab="🤖 模型">
          <div class="section">
            <h4>当前模型（全局切换）</h4>
            <NAlert type="info" :show-icon="false" class="scope-tip">
              切换后立即全局生效：所有对话和定时任务（无单独指定模型时）都使用此模型。
            </NAlert>
            <NSelect
              :value="settings.currentModel"
              :options="modelOptions"
              filterable
              placeholder="选择模型"
              class="model-select"
              @update:value="switchModel"
            />
            <p class="hint">当前: <code>{{ settings.currentModel }}</code></p>
          </div>

          <NDivider />

          <div class="section">
            <div class="section-header">
              <h4>已保存预设</h4>
              <NButton size="small" type="primary" @click="openCreateConfig">+ 新建预设</NButton>
            </div>
            <p class="hint">预设保存模型 ID + 参数，激活后全局生效（含定时任务）。</p>
            <NDataTable
              :columns="configColumns"
              :data="modelConfigs"
              size="small"
              :bordered="false"
              striped
              :max-height="240"
            />
          </div>
        </NTabPane>

        <!-- Tab 2: API 密钥 -->
        <NTabPane name="keys" tab="🔑 API 密钥">
          <div class="section">
            <p class="hint">
              每个服务商只需配置一次 API Key，同一服务商下的所有模型共用此密钥。
              密钥保存到本地数据库，应用重启后自动加载。
            </p>
          </div>

          <div class="provider-grid">
            <div
              v-for="p in PROVIDERS"
              :key="p.value"
              class="provider-card"
              :class="{ 'has-key': !!getKeyStatus(p.value) }"
            >
              <div class="provider-info">
                <span class="provider-name">{{ p.label }}</span>
                <NTag
                  v-if="getKeyStatus(p.value)"
                  type="success"
                  size="small"
                >已配置</NTag>
                <NTag v-else type="default" size="small">未配置</NTag>
              </div>
              <div class="provider-actions">
                <NButton
                  size="tiny"
                  :type="getKeyStatus(p.value) ? 'default' : 'primary'"
                  @click="getKeyStatus(p.value) ? openEditKey(getKeyStatus(p.value)!) : openAddKey(p.value)"
                >
                  {{ getKeyStatus(p.value) ? '修改' : '配置' }}
                </NButton>
                <NPopconfirm
                  v-if="getKeyStatus(p.value)"
                  @positive-click="deleteKey(p.value)"
                >
                  <template #trigger>
                    <NButton size="tiny" type="error" ghost>删除</NButton>
                  </template>
                  确定删除「{{ p.label }}」的 API Key？
                </NPopconfirm>
              </div>
            </div>
          </div>

          <NDivider />

          <div class="section">
            <NButton size="small" @click="openAddKey()">+ 添加其他 Provider</NButton>
          </div>
        </NTabPane>

        <!-- Tab 3: 工具全局管理 -->
        <NTabPane name="tools" tab="🔧 工具">
          <div class="section">
            <h4>全局工具开关</h4>
            <p class="hint">
              全局禁用后，该工具在所有会话中默认不可用。
              可在聊天界面的工具面板中为单个会话设置覆盖。
            </p>
            <div v-for="tool in globalToolStates" :key="tool.name" class="global-tool-row">
              <div class="global-tool-info">
                <code class="tool-code">{{ tool.name }}</code>
                <NTag
                  size="tiny"
                  :type="tool.global_enabled ? 'success' : 'default'"
                >{{ tool.global_enabled ? '全局启用' : '全局禁用' }}</NTag>
              </div>
              <NTooltip>
                <template #trigger>
                  <NSwitch
                    :value="tool.global_enabled"
                    :loading="togglingTool === tool.name"
                    @update:value="toggleGlobal(tool.name)"
                  />
                </template>
                {{ tool.global_enabled ? '点击全局禁用' : '点击全局启用' }}
              </NTooltip>
            </div>
          </div>
        </NTabPane>

        <!-- Tab 4: 提示词模板 -->
        <NTabPane name="templates" tab="📋 模板">
          <div class="section">
            <div class="section-header">
              <h4>提示词模板（{{ templates.length }}）</h4>
              <NButton size="small" type="primary" @click="openCreateTpl">+ 新建</NButton>
            </div>
            <p class="hint">在聊天输入框点击「📋 模板」可快速选用，Shift+Enter 保留换行。</p>
            <NDataTable
              :columns="tplColumns"
              :data="templates"
              size="small"
              :bordered="false"
              striped
              :max-height="360"
            />
          </div>
        </NTabPane>

      </NTabs>
    </NDrawerContent>
  </NDrawer>

  <!-- 模板 Modal -->
  <NModal
    v-model:show="showTplModal"
    preset="card"
    :title="editingTpl ? '编辑模板' : '新建提示词模板'"
    :style="{ width: '520px' }"
  >
    <NForm label-placement="left" label-width="80">
      <NFormItem label="名称">
        <NInput v-model:value="tplForm.name" placeholder="如：代码审查" />
      </NFormItem>
      <NFormItem label="分类">
        <NSelect
          v-model:value="tplForm.category"
          :options="CATEGORIES.map(c => ({ value: c, label: c }))"
          tag
          placeholder="选择或输入分类"
        />
      </NFormItem>
      <NFormItem label="模板内容">
        <NInput
          v-model:value="tplForm.content"
          type="textarea"
          :autosize="{ minRows: 6, maxRows: 16 }"
          placeholder="输入提示词模板，用 [占位符] 标记需要填写的部分"
        />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showTplModal = false">取消</NButton>
        <NButton type="primary" @click="saveTpl">保存</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- 模型预设 Modal -->
  <NModal
    v-model:show="showConfigModal"
    preset="card"
    :title="editingConfig ? '编辑预设' : '新建模型预设'"
    :style="{ width: '420px' }"
  >
    <NForm label-placement="left" label-width="90">
      <NFormItem label="预设名称">
        <NInput v-model:value="configForm.name" placeholder="如：快速助手" />
      </NFormItem>
      <NFormItem label="模型 ID">
        <NSelect
          v-model:value="configForm.model_id"
          :options="modelOptions"
          filterable
          placeholder="选择或输入模型 ID"
          tag
        />
      </NFormItem>
      <NFormItem label="Temperature">
        <NInputNumber v-model:value="configForm.temperature" :min="0" :max="2" :step="0.05" style="width:100%" />
      </NFormItem>
      <NFormItem label="Max Tokens">
        <NInputNumber v-model:value="configForm.max_tokens" :min="512" :max="200000" :step="512" style="width:100%" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showConfigModal = false">取消</NButton>
        <NButton type="primary" @click="saveConfig">保存</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- Provider Key Modal -->
  <NModal
    v-model:show="showKeyModal"
    preset="card"
    title="配置 Provider API Key"
    :style="{ width: '460px' }"
  >
    <NForm label-placement="left" label-width="90">
      <NFormItem label="Provider">
        <NSelect
          v-model:value="keyForm.provider"
          :options="PROVIDERS.map(p => ({ value: p.value, label: p.label }))"
          filterable
          tag
          placeholder="选择或输入 provider 名称"
        />
      </NFormItem>
      <NFormItem label="显示名称">
        <NInput v-model:value="keyForm.display_name" placeholder="如：OpenAI" />
      </NFormItem>
      <NFormItem label="API Key">
        <NInput
          v-model:value="keyForm.api_key"
          type="password"
          show-password-on="click"
          placeholder="留空则不修改已保存的 Key"
        />
      </NFormItem>
      <NFormItem label="API Base URL">
        <NInput
          v-model:value="keyForm.api_base"
          placeholder="可选，自定义 API 地址（如 Ollama: http://localhost:11434）"
        />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showKeyModal = false">取消</NButton>
        <NButton type="primary" @click="saveKey">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.section-header h4 { margin: 0; }
.hint { font-size: 12px; color: #999; margin: 6px 0 12px; }
.model-select { width: 100%; }
.scope-tip { margin-bottom: 10px; font-size: 12px; }
.tool-tags { display: flex; flex-wrap: wrap; gap: 6px; }

.provider-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.provider-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border: 1px solid #eee;
  border-radius: 8px;
  transition: border-color 0.2s;
}

.provider-card.has-key {
  border-color: #18a058;
  background: #f6ffed;
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.provider-name {
  font-size: 13px;
  font-weight: 500;
}

.provider-actions {
  display: flex;
  gap: 6px;
}

/* 全局工具行 */
.global-tool-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
}
.global-tool-row:last-child { border-bottom: none; }

.global-tool-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-code {
  font-family: monospace;
  font-size: 12px;
  color: #333;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
