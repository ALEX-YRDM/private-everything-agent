import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api, type ModelInfo } from '../api/http'

export const useSettingsStore = defineStore('settings', () => {
  const currentModel = ref<string>('gpt-4o')
  const models = ref<ModelInfo[]>([])
  const tools = ref<string[]>([])
  const config = ref<Record<string, unknown>>({})
  const showSettings = ref(false)

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

  async function setModel(model: string) {
    try {
      await api.config.setModel(model)
      currentModel.value = model
    } catch (e) {
      console.error('切换模型失败', e)
    }
  }

  async function init() {
    await Promise.all([loadModels(), loadConfig(), loadTools()])
  }

  return { currentModel, models, tools, config, showSettings, init, setModel, loadModels }
})
