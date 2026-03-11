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
}
