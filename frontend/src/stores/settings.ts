import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api, type ModelInfo, type ProviderKey, type SystemSkill, type UserSkill, type AppConfig } from '../api/http'
export type { SystemSkill, UserSkill }

export type { ProviderKey }

// ── Pinia Store ──────────────────────────────────────────────────────────────

export const useSettingsStore = defineStore('settings', () => {
  const currentModel = ref<string>('')
  const models = ref<ModelInfo[]>([])
  const tools = ref<string[]>([])
  const config = ref<Partial<AppConfig>>({})
  const showSettings = ref(false)
  const systemSkills = ref<SystemSkill[]>([])
  const userSkills = ref<UserSkill[]>([])

  const llmParams = ref({
    max_tokens: 4096,
    temperature: 0.1,
    context_window_tokens: 65536,
    max_iterations: 40,
  })

  // 从 DB 加载的 provider 列表（含模型）
  const providerGroups = ref<ProviderKey[]>([])

  // 由 providerGroups 派生出 NSelect 分组选项
  const modelSelectOptions = computed(() => {
    return providerGroups.value
      .filter((g) => g.models && g.models.length > 0)
      .map((g) => ({
        type: 'group' as const,
        label: g.display_name,
        key: g.provider,
        children: g.models.map((m) => ({ label: m.label, value: m.id })),
      }))
  })

  async function loadProviders() {
    try {
      const data = await api.providerKeys.list()
      providerGroups.value = data.keys
    } catch (e) {
      console.error('加载 Provider 列表失败', e)
    }
  }

  async function loadModels() {
    try {
      const data = await api.models.list()
      models.value = data.models
    } catch (e) {
      console.error('加载模型列表失败', e)
    }
  }

  async function loadConfig() {
    try {
      const data = await api.config.get()
      config.value = data
      if (data.model) currentModel.value = data.model
      llmParams.value.max_tokens = data.max_tokens
      llmParams.value.temperature = data.temperature
      llmParams.value.context_window_tokens = data.context_window_tokens
      llmParams.value.max_iterations = data.max_iterations
    } catch (e) {
      console.error('加载配置失败', e)
    }
  }

  async function updateLlmParams(params: Partial<typeof llmParams.value>) {
    const data = await api.config.updateLlmParams(params)
    llmParams.value.max_tokens = data.max_tokens
    llmParams.value.temperature = data.temperature
    llmParams.value.context_window_tokens = data.context_window_tokens
    llmParams.value.max_iterations = data.max_iterations
  }

  async function loadTools() {
    try {
      const data = await api.tools.list()
      tools.value = data.tools
    } catch (e) {
      console.error('加载工具列表失败', e)
    }
  }

  async function loadSkills() {
    try {
      const [sysData, userData] = await Promise.all([
        api.skills.listSystem(),
        api.skills.listUser(),
      ])
      systemSkills.value = sysData.skills
      userSkills.value = userData.skills
    } catch (e) {
      console.error('加载技能列表失败', e)
    }
  }

  async function setModel(modelId: string) {
    try {
      await api.models.switch(modelId)
      currentModel.value = modelId
    } catch (e) {
      console.error('切换模型失败', e)
      try {
        await api.config.setModel(modelId)
        currentModel.value = modelId
      } catch {
        // ignore
      }
    }
  }

  async function init() {
    await Promise.all([loadModels(), loadConfig(), loadTools(), loadProviders(), loadSkills()])
  }

  return {
    currentModel,
    models,
    tools,
    config,
    showSettings,
    providerGroups,
    modelSelectOptions,
    systemSkills,
    userSkills,
    llmParams,
    init,
    setModel,
    loadModels,
    loadProviders,
    loadSkills,
    updateLlmParams,
  }
})

// 兼容旧调用：buildModelSelectOptions() 等同于直接用 store.modelSelectOptions
// 保留导出以便 ChatPanel 等已有引用不需要大改
export function buildModelSelectOptions(groups?: ProviderKey[]) {
  if (!groups) return []
  return groups
    .filter((g) => g.models && g.models.length > 0)
    .map((g) => ({
      type: 'group' as const,
      label: g.display_name,
      key: g.provider,
      children: g.models.map((m) => ({ label: m.label, value: m.id })),
    }))
}
