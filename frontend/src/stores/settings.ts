import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api, type ModelInfo } from '../api/http'

// ── 完整常用模型列表（按 Provider 分组）────────────────────────────────────
export interface ModelGroup {
  provider: string
  label: string
  models: { id: string; label: string }[]
}

export const ALL_MODEL_GROUPS: ModelGroup[] = [
  {
    provider: 'openai',
    label: 'OpenAI',
    models: [
      { id: 'openai/o4-mini',        label: 'o4-mini' },
      { id: 'openai/o3',             label: 'o3' },
      { id: 'openai/o3-mini',        label: 'o3-mini' },
      { id: 'openai/o1',             label: 'o1' },
      { id: 'openai/o1-mini',        label: 'o1-mini' },
      { id: 'openai/gpt-4.1',        label: 'GPT-4.1' },
      { id: 'openai/gpt-4.1-mini',   label: 'GPT-4.1 mini' },
      { id: 'openai/gpt-4o',         label: 'GPT-4o' },
      { id: 'openai/gpt-4o-mini',    label: 'GPT-4o mini' },
      { id: 'openai/gpt-4-turbo',    label: 'GPT-4 Turbo' },
      { id: 'openai/gpt-3.5-turbo',  label: 'GPT-3.5 Turbo' },
    ],
  },
  {
    provider: 'anthropic',
    label: 'Anthropic',
    models: [
      { id: 'anthropic/claude-opus-4-20250514',    label: 'Claude Opus 4' },
      { id: 'anthropic/claude-sonnet-4-20250514',  label: 'Claude Sonnet 4' },
      { id: 'anthropic/claude-3-7-sonnet-20250219',label: 'Claude 3.7 Sonnet' },
      { id: 'anthropic/claude-3-5-sonnet-20241022',label: 'Claude 3.5 Sonnet' },
      { id: 'anthropic/claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
    ],
  },
  {
    provider: 'gemini',
    label: 'Google Gemini',
    models: [
      { id: 'gemini/gemini-2.5-pro-preview-05-06', label: 'Gemini 2.5 Pro' },
      { id: 'gemini/gemini-2.0-flash',             label: 'Gemini 2.0 Flash' },
      { id: 'gemini/gemini-2.0-flash-lite',        label: 'Gemini 2.0 Flash Lite' },
      { id: 'gemini/gemini-1.5-pro',               label: 'Gemini 1.5 Pro' },
      { id: 'gemini/gemini-1.5-flash',             label: 'Gemini 1.5 Flash' },
    ],
  },
  {
    provider: 'deepseek',
    label: 'DeepSeek',
    models: [
      { id: 'deepseek/deepseek-chat',      label: 'DeepSeek Chat (V3)' },
      { id: 'deepseek/deepseek-reasoner',  label: 'DeepSeek Reasoner (R1)' },
    ],
  },
  {
    provider: 'xai',
    label: 'xAI (Grok)',
    models: [
      { id: 'xai/grok-3',       label: 'Grok 3' },
      { id: 'xai/grok-3-mini',  label: 'Grok 3 Mini' },
      { id: 'xai/grok-2-1212',  label: 'Grok 2' },
    ],
  },
  {
    provider: 'groq',
    label: 'Groq',
    models: [
      { id: 'groq/llama-3.3-70b-versatile',    label: 'Llama 3.3 70B' },
      { id: 'groq/llama-3.1-8b-instant',       label: 'Llama 3.1 8B (fast)' },
      { id: 'groq/mixtral-8x7b-32768',         label: 'Mixtral 8x7B' },
      { id: 'groq/gemma2-9b-it',               label: 'Gemma2 9B' },
      { id: 'groq/qwen-qwq-32b',               label: 'Qwen QwQ 32B' },
    ],
  },
  {
    provider: 'mistral',
    label: 'Mistral AI',
    models: [
      { id: 'mistral/mistral-large-latest',  label: 'Mistral Large' },
      { id: 'mistral/mistral-small-latest',  label: 'Mistral Small' },
      { id: 'mistral/codestral-latest',      label: 'Codestral' },
      { id: 'mistral/mistral-nemo',          label: 'Mistral Nemo' },
    ],
  },
  {
    provider: 'together_ai',
    label: 'Together AI',
    models: [
      { id: 'together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo',      label: 'Llama 3.3 70B Turbo' },
      { id: 'together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo',  label: 'Llama 3.1 8B Turbo' },
      { id: 'together_ai/Qwen/Qwen2.5-72B-Instruct-Turbo',              label: 'Qwen 2.5 72B Turbo' },
      { id: 'together_ai/deepseek-ai/DeepSeek-R1',                      label: 'DeepSeek R1' },
    ],
  },
  {
    provider: 'openrouter',
    label: 'OpenRouter',
    models: [
      { id: 'openrouter/google/gemini-2.0-flash-001',          label: 'Gemini 2.0 Flash' },
      { id: 'openrouter/anthropic/claude-3.5-sonnet',          label: 'Claude 3.5 Sonnet' },
      { id: 'openrouter/meta-llama/llama-3.3-70b-instruct',    label: 'Llama 3.3 70B' },
      { id: 'openrouter/deepseek/deepseek-r1',                 label: 'DeepSeek R1' },
      { id: 'openrouter/qwen/qwq-32b',                         label: 'QwQ 32B' },
    ],
  },
  {
    provider: 'perplexity',
    label: 'Perplexity',
    models: [
      { id: 'perplexity/sonar-pro',    label: 'Sonar Pro' },
      { id: 'perplexity/sonar',        label: 'Sonar' },
    ],
  },
  {
    provider: 'ollama',
    label: 'Ollama (本地)',
    models: [
      { id: 'ollama/llama3.3',         label: 'Llama 3.3' },
      { id: 'ollama/qwen2.5:72b',      label: 'Qwen 2.5 72B' },
      { id: 'ollama/deepseek-r1:14b',  label: 'DeepSeek R1 14B' },
      { id: 'ollama/mistral',          label: 'Mistral' },
    ],
  },
  {
    provider: 'volcengine',
    label: '字节跳动 (火山引擎)',
    models: [
      { id: 'volcengine/doubao-pro-32k',  label: 'Doubao Pro 32K' },
      { id: 'volcengine/doubao-lite-32k', label: 'Doubao Lite 32K' },
    ],
  },
  {
    provider: 'moonshot',
    label: '月之暗面 (Kimi)',
    models: [
      { id: 'moonshot/moonshot-v1-128k', label: 'Moonshot v1 128K' },
      { id: 'moonshot/moonshot-v1-32k',  label: 'Moonshot v1 32K' },
    ],
  },
]

// 展开成 SelectOption 格式（分组）
export function buildModelSelectOptions() {
  return ALL_MODEL_GROUPS.map((g) => ({
    type: 'group' as const,
    label: g.label,
    key: g.provider,
    children: g.models.map((m) => ({ label: m.label, value: m.id })),
  }))
}

// ── Pinia Store ──────────────────────────────────────────────────────────────

export const useSettingsStore = defineStore('settings', () => {
  const currentModel = ref<string>('openai/gpt-4o')
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

  async function setModel(modelId: string) {
    try {
      await api.models.switch(modelId)
      currentModel.value = modelId
    } catch (e) {
      console.error('切换模型失败', e)
      // 降级：尝试旧接口
      try {
        await api.config.setModel(modelId)
        currentModel.value = modelId
      } catch {
        // ignore
      }
    }
  }

  async function init() {
    await Promise.all([loadModels(), loadConfig(), loadTools()])
  }

  return { currentModel, models, tools, config, showSettings, init, setModel, loadModels }
})
