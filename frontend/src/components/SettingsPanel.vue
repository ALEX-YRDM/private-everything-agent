<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import {
  NDrawer, NDrawerContent, NSelect, NTag, NButton,
  NModal, NForm, NFormItem, NInput,
  NDataTable, useMessage, NTabs, NTabPane, NSpace, NPopconfirm,
  NAlert, NSwitch, NTooltip, NSpin, NCollapse, NCollapseItem,
  NEmpty, NBadge,
} from 'naive-ui'
import { useSettingsStore } from '../stores/settings'
import { api, type ProviderKey, type ProviderModel, type PromptTemplate, type ToolState } from '../api/http'

const settings = useSettingsStore()
const message = useMessage()

// ── 全局模型切换 ─────────────────────────────────────────────────────────────
async function switchModel(modelId: string) {
  try {
    await settings.setModel(modelId)
    message.success(`已切换到 ${modelId}（全局生效）`)
  } catch {
    message.error('模型切换失败')
  }
}

// ── 服务商管理 ───────────────────────────────────────────────────────────────

// LiteLLM 已知的标准 provider（有内置路由，不需要 api_base）
const STANDARD_PROVIDERS = new Set([
  'openai','anthropic','gemini','deepseek','groq','mistral',
  'together_ai','openrouter','xai','perplexity','cohere',
  'azure','volcengine','moonshot','zhipuai','baidu','dashscope','ollama',
])

// 编辑 Provider Key/信息的弹窗
const showProviderModal = ref(false)
const isNewProvider = ref(false)
const providerForm = ref({ provider: '', display_name: '', api_key: '', api_base: '' })
const savingProvider = ref(false)

// 当前 provider 是否为自定义（非标准）
const isCustomProvider = computed(() =>
  !!providerForm.value.provider && !STANDARD_PROVIDERS.has(providerForm.value.provider.toLowerCase())
)

const providerIdFeedback = computed(() => {
  if (!providerForm.value.provider) return ''
  if (isCustomProvider.value) {
    return '⚠️ 非标准 Provider，LiteLLM 无内置路由 — 必须填写 API Base URL'
  }
  return `✓ 标准 Provider，LiteLLM 自动路由，模型 ID 格式：${providerForm.value.provider}/模型名`
})

function openAddProvider() {
  isNewProvider.value = true
  providerForm.value = { provider: '', display_name: '', api_key: '', api_base: '' }
  showProviderModal.value = true
}

function openEditProvider(pk: ProviderKey) {
  isNewProvider.value = false
  providerForm.value = {
    provider: pk.provider,
    display_name: pk.display_name,
    api_key: '',       // 留空=不修改
    api_base: pk.api_base || '',
  }
  showProviderModal.value = true
}

async function saveProvider() {
  if (!providerForm.value.provider.trim() || !providerForm.value.display_name.trim()) {
    message.warning('请填写 Provider ID 和显示名称')
    return
  }
  // 自定义（非标准）provider 必须填 api_base，否则 LiteLLM 不知道发往哪个地址
  if (isCustomProvider.value && !providerForm.value.api_base.trim()) {
    message.warning('自定义 Provider 必须填写 API Base URL（服务地址），否则调用时会报错')
    return
  }
  savingProvider.value = true
  try {
    await api.providerKeys.upsert({
      provider: providerForm.value.provider.trim(),
      display_name: providerForm.value.display_name.trim(),
      api_key: providerForm.value.api_key || null,
      api_base: providerForm.value.api_base || null,
    })
    showProviderModal.value = false
    await settings.loadProviders()
    message.success(`Provider「${providerForm.value.provider}」已保存`)
  } catch (e) { message.error(String(e)) }
  finally { savingProvider.value = false }
}

async function deleteProvider(provider: string) {
  try {
    await api.providerKeys.delete(provider)
    await settings.loadProviders()
    message.success('已删除')
  } catch (e) { message.error(String(e)) }
}

// ── 模型管理（某 provider 下的模型列表）────────────────────────────────────

const showModelModal = ref(false)
const editingModelProvider = ref('')
const editingModelIndex = ref<number | null>(null)  // null = 新增
const modelForm = ref({ id: '', label: '' })
const testingModel = ref('')
const testResults = ref<Record<string, 'ok' | 'fail' | 'testing'>>({})

function openAddModel(provider: string) {
  editingModelProvider.value = provider
  editingModelIndex.value = null
  modelForm.value = { id: '', label: '' }
  showModelModal.value = true
}

function openEditModel(provider: string, index: number, model: ProviderModel) {
  editingModelProvider.value = provider
  editingModelIndex.value = index
  modelForm.value = { id: model.id, label: model.label }
  showModelModal.value = true
}

async function saveModel() {
  if (!modelForm.value.id.trim() || !modelForm.value.label.trim()) {
    message.warning('请填写模型 ID 和显示名称')
    return
  }
  const pk = settings.providerGroups.find(p => p.provider === editingModelProvider.value)
  if (!pk) return
  const models = [...pk.models]
  const newModel: ProviderModel = { id: modelForm.value.id.trim(), label: modelForm.value.label.trim() }
  if (editingModelIndex.value === null) {
    models.push(newModel)
  } else {
    models[editingModelIndex.value] = newModel
  }
  try {
    await api.providerKeys.updateModels(editingModelProvider.value, models)
    showModelModal.value = false
    await settings.loadProviders()
    message.success('模型已保存')
  } catch (e) { message.error(String(e)) }
}

async function deleteModel(provider: string, index: number) {
  const pk = settings.providerGroups.find(p => p.provider === provider)
  if (!pk) return
  const models = pk.models.filter((_, i) => i !== index)
  try {
    await api.providerKeys.updateModels(provider, models)
    await settings.loadProviders()
    message.success('已删除')
  } catch (e) { message.error(String(e)) }
}

async function testModel(modelId: string) {
  testResults.value[modelId] = 'testing'
  testingModel.value = modelId
  try {
    const res = await api.models.test(modelId)
    testResults.value[modelId] = res.ok ? 'ok' : 'fail'
    if (res.ok) {
      message.success(`模型 ${modelId} 调用正常 ✓`)
    } else {
      message.error(`调用失败: ${res.error || '未知错误'}`)
    }
  } catch (e) {
    testResults.value[modelId] = 'fail'
    message.error(`调用失败: ${String(e)}`)
  } finally {
    testingModel.value = ''
  }
}

// 用于快速在模型下拉框预填 provider 前缀
function autoFillModelId() {
  if (!modelForm.value.id && editingModelProvider.value) {
    modelForm.value.id = editingModelProvider.value + '/'
  }
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
  await Promise.all([loadTemplates(), loadGlobalToolStates()])
})
</script>

<template>
  <NDrawer
    :show="settings.showSettings"
    @update:show="settings.showSettings = $event"
    :width="580"
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
              :options="settings.modelSelectOptions"
              filterable
              tag
              placeholder="选择或输入模型 ID"
              class="model-select"
              @update:value="switchModel"
            />
            <p class="hint">
              当前: <code>{{ settings.currentModel }}</code>
              &nbsp;·&nbsp;
              <span style="color:#999">
                在「🔑 服务商」标签页中管理 API Key 和模型列表
              </span>
            </p>
          </div>
        </NTabPane>

        <!-- Tab 2: 服务商管理 -->
        <NTabPane name="providers" tab="🔑 服务商">
          <div class="section">
            <div class="section-header">
              <div>
                <h4 style="margin:0">服务商 &amp; 模型管理</h4>
                <p class="hint" style="margin:4px 0 0">
                  每个服务商配置一次 API Key，下挂多个模型；模型列表可自由增删。
                </p>
              </div>
              <NButton size="small" type="primary" @click="openAddProvider">
                + 新增服务商
              </NButton>
            </div>
          </div>

          <NEmpty
            v-if="settings.providerGroups.length === 0"
            description="暂无服务商配置，点击「新增服务商」添加"
            style="margin: 24px 0"
          />

          <NCollapse v-else display-directive="show">
            <NCollapseItem
              v-for="pk in settings.providerGroups"
              :key="pk.provider"
              :name="pk.provider"
            >
              <template #header>
                <div class="provider-header">
                  <span class="provider-name">{{ pk.display_name }}</span>
                  <code class="provider-id">{{ pk.provider }}</code>
                  <NTag v-if="pk.api_key" type="success" size="small">Key ✓</NTag>
                  <NTag v-else type="default" size="small">无 Key</NTag>
                  <NTag v-if="pk.api_base" size="small" type="info">自定义地址</NTag>
                  <NBadge :value="pk.models.length" :max="99" type="info" style="margin-left:4px">
                    <span style="font-size:11px;color:#999">个模型</span>
                  </NBadge>
                </div>
              </template>
              <template #header-extra>
                <NSpace size="small" @click.stop>
                  <NButton size="tiny" @click.stop="openEditProvider(pk)">编辑 Key</NButton>
                  <NPopconfirm @positive-click="deleteProvider(pk.provider)">
                    <template #trigger>
                      <NButton size="tiny" type="error" ghost @click.stop>删除</NButton>
                    </template>
                    确定删除服务商「{{ pk.display_name }}」及其所有模型？
                  </NPopconfirm>
                </NSpace>
              </template>

              <!-- 模型列表 -->
              <div class="models-section">
                <div class="models-header">
                  <span class="models-title">模型列表（{{ pk.models.length }}）</span>
                  <NButton size="tiny" type="primary" ghost @click="openAddModel(pk.provider)">
                    + 添加模型
                  </NButton>
                </div>

                <NEmpty v-if="pk.models.length === 0" description="暂无模型，点击添加" :style="{ margin: '12px 0' }" />

                <div v-for="(model, idx) in pk.models" :key="model.id" class="model-row">
                  <div class="model-info">
                    <span class="model-label">{{ model.label }}</span>
                    <code class="model-id-text">{{ model.id }}</code>
                  </div>
                  <div class="model-actions">
                    <!-- 测试状态 -->
                    <NTag
                      v-if="testResults[model.id] === 'ok'"
                      type="success" size="tiny"
                    >✓ 可用</NTag>
                    <NTag
                      v-else-if="testResults[model.id] === 'fail'"
                      type="error" size="tiny"
                    >✗ 失败</NTag>
                    <NSpin v-else-if="testResults[model.id] === 'testing'" size="small" />

                    <NTooltip>
                      <template #trigger>
                        <NButton
                          size="tiny"
                          :loading="testingModel === model.id"
                          @click="testModel(model.id)"
                        >测试</NButton>
                      </template>
                      发送一条最小请求校验模型是否可正常调用
                    </NTooltip>
                    <NButton size="tiny" @click="openEditModel(pk.provider, idx, model)">编辑</NButton>
                    <NPopconfirm @positive-click="deleteModel(pk.provider, idx)">
                      <template #trigger>
                        <NButton size="tiny" type="error" ghost>删除</NButton>
                      </template>
                      确定删除模型「{{ model.label }}」？
                    </NPopconfirm>
                  </div>
                </div>
              </div>
            </NCollapseItem>
          </NCollapse>
        </NTabPane>

        <!-- Tab 3: 工具全局管理 -->
        <NTabPane name="tools" tab="🔧 工具">
          <div class="section">
            <h4>全局工具开关</h4>
            <p class="hint">
              全局禁用后，该工具在所有会话中默认不可用。
              可在聊天界面的「🔧 工具」面板中为单个会话设置覆盖。
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
            <p class="hint">在聊天输入框点击「📋 模板」可快速选用。</p>
            <NDataTable
              :columns="tplColumns"
              :data="templates"
              size="small"
              :bordered="false"
              striped
              :max-height="400"
            />
          </div>
        </NTabPane>

      </NTabs>
    </NDrawerContent>
  </NDrawer>

  <!-- 服务商 Modal -->
  <NModal
    v-model:show="showProviderModal"
    preset="card"
    :title="isNewProvider ? '新增服务商' : '编辑服务商'"
    :style="{ width: '500px' }"
  >
    <!-- 使用 OpenAI 兼容服务的引导提示 -->
    <NAlert
      type="info"
      :show-icon="true"
      style="margin-bottom:14px;font-size:12px"
      title="接入 OpenAI 兼容的自定义服务"
    >
      <div>将 <b>Provider ID</b> 设为 <code>openai</code>，在 <b>API Base URL</b> 填入你的服务地址（需包含 <code>/v1</code>，如 <code>http://localhost:1234/v1</code>），
      模型 ID 格式为 <code>openai/你的模型名</code>。</div>
      <div style="margin-top:4px;color:#888">
        支持 LM Studio、Ollama (openai 模式)、OneAPI、vLLM 等所有 OpenAI 兼容接口（vLLM 示例：<code>http://host:port/v1</code>）。
      </div>
    </NAlert>

    <NForm label-placement="left" label-width="110">
      <NFormItem label="Provider ID" :feedback="providerIdFeedback" :validation-status="isCustomProvider ? 'warning' : undefined">
        <NInput
          v-model:value="providerForm.provider"
          :disabled="!isNewProvider"
          placeholder="如：openai / deepseek / my_service"
        />
      </NFormItem>
      <NFormItem label="显示名称">
        <NInput v-model:value="providerForm.display_name" placeholder="如：OpenAI / 我的本地模型" />
      </NFormItem>
      <NFormItem label="API Key">
        <NInput
          v-model:value="providerForm.api_key"
          type="password"
          show-password-on="click"
          placeholder="留空则不修改已保存的 Key"
        />
      </NFormItem>
      <NFormItem
        label="API Base URL"
        :feedback="isCustomProvider && !providerForm.api_base ? '⚠️ 自定义 Provider 必须填写服务地址' : ''"
        :validation-status="isCustomProvider && !providerForm.api_base ? 'error' : undefined"
      >
        <NInput
          v-model:value="providerForm.api_base"
          :placeholder="isCustomProvider
            ? '必填：http://your-server/v1'
            : '可选，如 Ollama: http://localhost:11434'"
        />
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
  <NModal
    v-model:show="showModelModal"
    preset="card"
    :title="editingModelIndex === null ? `为 ${editingModelProvider} 添加模型` : '编辑模型'"
    :style="{ width: '460px' }"
  >
    <NForm label-placement="left" label-width="90">
      <NFormItem label="模型 ID">
        <NInput
          v-model:value="modelForm.id"
          placeholder="如：openai/gpt-4o"
          @focus="autoFillModelId"
        />
        <template #feedback>
          <span style="font-size:11px;color:#999">
            格式：{provider}/{model_name}，参考 LiteLLM 文档
          </span>
        </template>
      </NFormItem>
      <NFormItem label="显示名称">
        <NInput v-model:value="modelForm.label" placeholder="如：GPT-4o" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showModelModal = false">取消</NButton>
        <NButton type="primary" @click="saveModel">保存</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- 提示词模板 Modal -->
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
</template>

<style scoped>
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}
.section-header h4 { margin: 0; }
.hint { font-size: 12px; color: #999; margin: 6px 0 12px; }
.model-select { width: 100%; }
.scope-tip { margin-bottom: 10px; font-size: 12px; }

/* 服务商折叠头部 */
.provider-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.provider-name {
  font-weight: 600;
  font-size: 14px;
}

.provider-id {
  font-size: 11px;
  color: #888;
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 4px;
  font-family: monospace;
}

/* 模型列表 */
.models-section {
  padding: 4px 0 8px;
}

.models-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.models-title {
  font-size: 13px;
  font-weight: 500;
  color: #555;
}

.model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background 0.15s;
  gap: 8px;
}

.model-row:hover { background: #f9fafb; }

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.model-label {
  font-size: 13px;
  font-weight: 500;
  color: #1a1a1a;
}

.model-id-text {
  font-size: 11px;
  color: #888;
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
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
