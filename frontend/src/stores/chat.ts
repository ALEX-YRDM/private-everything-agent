import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api, type Session, type Message } from '../api/http'
import { AgentWebSocket, type StreamEvent } from '../api/websocket'

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  reasoning?: string
  toolCalls?: ToolCallDisplay[]
  toolResults?: Record<string, string>
  isStreaming?: boolean
  timestamp: number
}

export interface ToolCallDisplay {
  id: string
  name: string
  args: Record<string, unknown>
}

const TASK_TOOLS = new Set(['create_task', 'delete_task', 'update_task'])

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<DisplayMessage[]>([])
  const isStreaming = ref(false)
  const streamingMessage = ref<DisplayMessage | null>(null)
  const wsMap = new Map<string, AgentWebSocket>()

  /** 每当任务工具执行完毕，此计数器 +1，供 SchedulerPanel 监听刷新。 */
  const tasksChangedAt = ref(0)
  /** 最近一次收到的定时任务广播通知（App.vue 监听并显示 toast）。 */
  const lastTaskNotification = ref<{ task_name: string; status: string; message: string } | null>(null)

  const currentSession = computed(() =>
    sessions.value.find((s) => s.id === currentSessionId.value) || null
  )

  async function loadSessions() {
    try {
      const data = await api.sessions.list()
      sessions.value = data.sessions
    } catch (e) {
      console.error('加载会话列表失败', e)
    }
  }

  async function createSession(title = '新会话') {
    const session = await api.sessions.create(title)
    sessions.value.unshift(session)
    await switchSession(session.id)
    return session
  }

  async function deleteSession(id: string) {
    await api.sessions.delete(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    if (currentSessionId.value === id) {
      currentSessionId.value = null
      messages.value = []
      const first = sessions.value[0]
      if (first) {
        await switchSession(first.id)
      }
    }
  }

  async function switchSession(id: string) {
    if (currentSessionId.value === id) return
    currentSessionId.value = id
    messages.value = []
    streamingMessage.value = null
    isStreaming.value = false

    try {
      const data = await api.sessions.getMessages(id)
      messages.value = convertMessages(data.messages)
    } catch (e) {
      console.error('加载消息失败', e)
    }

    connectWS(id)
  }

  function convertMessages(rawMessages: Message[]): DisplayMessage[] {
    const result: DisplayMessage[] = []
    const tcMap = new Map<string, ToolCallDisplay[]>()
    const trMap = new Map<string, Record<string, string>>()

    for (const m of rawMessages) {
      if (m.role === 'assistant') {
        const toolCalls: ToolCallDisplay[] = []
        if (m.tool_calls) {
          try {
            const parsed = JSON.parse(m.tool_calls) as Array<{
              id: string
              function: { name: string; arguments: string }
            }>
            for (const tc of parsed) {
              toolCalls.push({
                id: tc.id,
                name: tc.function.name,
                args: JSON.parse(tc.function.arguments || '{}'),
              })
            }
          } catch {}
        }
        const msg: DisplayMessage = {
          id: `msg-${m.id}`,
          role: 'assistant',
          content: m.content || '',
          reasoning: m.reasoning || undefined,
          toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
          toolResults: {},
          timestamp: new Date(m.created_at).getTime(),
        }
        result.push(msg)
        if (toolCalls.length > 0) {
          tcMap.set(`msg-${m.id}`, toolCalls)
          trMap.set(`msg-${m.id}`, {})
        }
      } else if (m.role === 'tool' && m.tool_call_id) {
        const toolCallId = m.tool_call_id
        for (let i = result.length - 1; i >= 0; i--) {
          const msg = result[i]
          if (msg !== undefined && msg.role === 'assistant' && msg.toolResults !== undefined) {
            msg.toolResults[toolCallId] = m.content || ''
            break
          }
        }
      } else if (m.role === 'user') {
        result.push({
          id: `msg-${m.id}`,
          role: 'user',
          content: m.content || '',
          timestamp: new Date(m.created_at).getTime(),
        })
      }
    }
    return result
  }

  function connectWS(sessionId: string) {
    const existing = wsMap.get(sessionId)
    if (existing?.isConnected) return

    const ws = new AgentWebSocket(sessionId)
    wsMap.set(sessionId, ws)

    ws.connect(
      (event) => handleStreamEvent(sessionId, event),
      () => {
        wsMap.delete(sessionId)
      }
    ).catch((e) => console.error('WebSocket 连接失败', e))
  }

  function handleStreamEvent(sessionId: string, event: StreamEvent) {
    if (sessionId !== currentSessionId.value) return

    if (event.type === 'content_delta') {
      if (!streamingMessage.value) {
        streamingMessage.value = {
          id: `streaming-${Date.now()}`,
          role: 'assistant',
          content: '',
          toolCalls: [],
          toolResults: {},
          isStreaming: true,
          timestamp: Date.now(),
        }
      }
      streamingMessage.value.content += event.content
    } else if (event.type === 'thinking') {
      if (!streamingMessage.value) {
        streamingMessage.value = {
          id: `streaming-${Date.now()}`,
          role: 'assistant',
          content: '',
          reasoning: '',
          toolCalls: [],
          toolResults: {},
          isStreaming: true,
          timestamp: Date.now(),
        }
      }
      streamingMessage.value.reasoning = (streamingMessage.value.reasoning || '') + event.content
    } else if (event.type === 'tool_call') {
      if (!streamingMessage.value) {
        streamingMessage.value = {
          id: `streaming-${Date.now()}`,
          role: 'assistant',
          content: '',
          toolCalls: [],
          toolResults: {},
          isStreaming: true,
          timestamp: Date.now(),
        }
      }
      streamingMessage.value.toolCalls!.push({
        id: event.id,
        name: event.name,
        args: event.args,
      })
    } else if (event.type === 'tool_result') {
      // 找到最后一个有相同 name 的工具调用，把结果写入
      if (streamingMessage.value?.toolCalls) {
        const tc = [...streamingMessage.value.toolCalls].reverse().find((t) => t.name === event.name)
        if (tc) {
          streamingMessage.value.toolResults![tc.id] = event.content
        }
      }
      // 任务工具执行完毕 → 通知 SchedulerPanel 刷新
      if (TASK_TOOLS.has(event.name)) {
        tasksChangedAt.value++
      }
    } else if (event.type === 'done') {
      if (streamingMessage.value) {
        streamingMessage.value.isStreaming = false
        messages.value.push({ ...streamingMessage.value })
        streamingMessage.value = null
      }
      isStreaming.value = false

      // 刷新会话列表（更新 updated_at）
      loadSessions()
    } else if (event.type === 'error') {
      isStreaming.value = false
      streamingMessage.value = null
      console.error('Agent 错误:', event.message)
    } else if (event.type === 'task_notification') {
      // 定时任务完成通知：触发 SchedulerPanel 刷新
      tasksChangedAt.value++
      // 将通知暴露给外部（App.vue 用于显示 toast）
      lastTaskNotification.value = event
    }
  }

  async function sendMessage(content: string) {
    if (!currentSessionId.value || isStreaming.value) return

    messages.value.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    })

    isStreaming.value = true
    streamingMessage.value = null

    const sessionId = currentSessionId.value
    let ws = wsMap.get(sessionId)
    if (!ws || !ws.isConnected) {
      ws = new AgentWebSocket(sessionId)
      wsMap.set(sessionId, ws)
      await ws.connect(
        (event) => handleStreamEvent(sessionId, event),
        () => wsMap.delete(sessionId)
      )
    }
    ws.sendMessage(content)
  }

  function stopStreaming() {
    if (!currentSessionId.value) return
    const ws = wsMap.get(currentSessionId.value)
    ws?.stop()
    isStreaming.value = false
    streamingMessage.value = null
  }

  async function renameSession(id: string, title: string) {
    await api.sessions.updateTitle(id, title)
    const s = sessions.value.find((s) => s.id === id)
    if (s) s.title = title
  }

  async function init() {
    await loadSessions()
    const first = sessions.value[0]
    if (first) {
      await switchSession(first.id)
    }
  }

  return {
    sessions,
    currentSessionId,
    currentSession,
    messages,
    isStreaming,
    streamingMessage,
    tasksChangedAt,
    lastTaskNotification,
    init,
    loadSessions,
    createSession,
    deleteSession,
    switchSession,
    sendMessage,
    stopStreaming,
    renameSession,
  }
})
