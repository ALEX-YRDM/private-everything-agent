import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api, type ModelInfo, type ProviderKey } from '../api/http'

export type { ProviderKey }

// ── Pinia Store ──────────────────────────────────────────────────────────────

export const useSettingsStore = defineStore('settings', () => {
  const currentModel = ref<string>('openai/gpt-4o')
  const models = ref<ModelInfo[]>([])
  const tools = ref<string[]>([])
  const config = ref<Record<string, unknown>>({})
  const showSettings = ref(false)

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
      if (data.model) {
        currentModel.value = data.model as string
      }
    } catch (e) {
      console.error('加载配置失败', e)
    }
  }

  async function loadTools() {
    try {
      const data = await api.tools.list()
      tools.value = data.tools
    } catch (e) {
      console.error('加载工具列表失败', e)
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
    await Promise.all([loadModels(), loadConfig(), loadTools(), loadProviders()])
  }

  return {
    currentModel,
    models,
    tools,
    config,
    showSettings,
    providerGroups,
    modelSelectOptions,
    init,
    setModel,
    loadModels,
    loadProviders,
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
