const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(err || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export interface Session {
  id: string
  title: string
  model: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  session_id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string | null
  tool_calls: string | null
  tool_call_id: string | null
  tool_name: string | null
  reasoning: string | null
  created_at: string
}

export interface ModelInfo {
  id: string
  provider: string
}

export interface ModelConfig {
  id: number
  name: string
  model_id: string
  temperature: number
  max_tokens: number
  is_default: number
  enabled: number
  created_at: string
}

export interface ProviderKey {
  id: number
  provider: string
  display_name: string
  api_key: string | null
  api_key_masked: string | null
  api_base: string | null
  updated_at: string
}

export interface ScheduledTask {
  id: number
  name: string
  cron_expr: string
  prompt: string
  model_id: string | null
  enabled: number
  last_run_at: string | null
  last_status: string | null
  session_id: string | null
  created_at: string
}

export const api = {
  sessions: {
    list: () => request<{ sessions: Session[] }>('/api/sessions'),
    create: (title = '新会话', model?: string) =>
      request<Session>('/api/sessions', {
        method: 'POST',
        body: JSON.stringify({ title, model }),
      }),
    delete: (id: string) =>
      request<{ ok: boolean }>(`/api/sessions/${id}`, { method: 'DELETE' }),
    getMessages: (id: string) =>
      request<{ messages: Message[] }>(`/api/sessions/${id}/messages`),
    updateTitle: (id: string, title: string) =>
      request<{ ok: boolean }>(`/api/sessions/${id}/title`, {
        method: 'PUT',
        body: JSON.stringify({ title }),
      }),
  },
  models: {
    list: () => request<{ models: ModelInfo[] }>('/api/models'),
    switch: (model_id: string) =>
      request<{ ok: boolean; active_model: string; provider: string }>('/api/models/switch', {
        method: 'POST',
        body: JSON.stringify({ model_id }),
      }),
  },
  tools: {
    list: () => request<{ tools: string[] }>('/api/tools'),
  },
  config: {
    get: () => request<Record<string, unknown>>('/api/config'),
    setModel: (model: string) =>
      request<{ ok: boolean; model: string }>('/api/config/model', {
        method: 'PUT',
        body: JSON.stringify({ model }),
      }),
  },
  providerKeys: {
    list: () => request<{ keys: ProviderKey[] }>('/api/provider-keys'),
    upsert: (data: { provider: string; display_name: string; api_key?: string; api_base?: string }) =>
      request<{ ok: boolean; row: ProviderKey }>('/api/provider-keys', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    delete: (provider: string) =>
      request<{ ok: boolean }>(`/api/provider-keys/${provider}`, { method: 'DELETE' }),
  },
  modelConfigs: {
    list: () => request<{ configs: ModelConfig[] }>('/api/model-configs'),
    create: (data: { name: string; model_id: string; temperature?: number; max_tokens?: number }) =>
      request<ModelConfig>('/api/model-configs', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<ModelConfig>) =>
      request<ModelConfig>(`/api/model-configs/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<{ ok: boolean }>(`/api/model-configs/${id}`, { method: 'DELETE' }),
    activate: (id: number) =>
      request<{ ok: boolean; active_model: string }>(`/api/model-configs/${id}/activate`, { method: 'POST' }),
  },
  tasks: {
    list: () => request<{ tasks: ScheduledTask[] }>('/api/tasks'),
    create: (data: { name: string; cron_expr: string; prompt: string; model_id?: string }) =>
      request<ScheduledTask>('/api/tasks', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<ScheduledTask>) =>
      request<ScheduledTask>(`/api/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<{ ok: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' }),
    runNow: (id: number) =>
      request<{ ok: boolean; message: string }>(`/api/tasks/${id}/run`, { method: 'POST' }),
  },
}
