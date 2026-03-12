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

interface SessionState {
  messages: DisplayMessage[]
  isStreaming: boolean
  streamingMessage: DisplayMessage | null
  loaded: boolean
}

const TASK_TOOLS = new Set(['create_task', 'delete_task', 'update_task'])

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const sessionStates = ref<Record<string, SessionState>>({})
  const wsMap = new Map<string, AgentWebSocket>()

  /** 每当任务工具执行完毕，此计数器 +1，供 SchedulerPanel 监听刷新。 */
  const tasksChangedAt = ref(0)
  /** 最近一次收到的定时任务广播通知（App.vue 监听并显示 toast）。 */
  const lastTaskNotification = ref<{ task_name: string; status: string; message: string } | null>(null)

  const currentSession = computed(() =>
    sessions.value.find((s) => s.id === currentSessionId.value) || null
  )

  // 当前会话的状态，派生自 sessionStates（per-session 状态 Map）
  const messages = computed(() =>
    currentSessionId.value ? (sessionStates.value[currentSessionId.value]?.messages ?? []) : []
  )
  const isStreaming = computed(() =>
    currentSessionId.value ? (sessionStates.value[currentSessionId.value]?.isStreaming ?? false) : false
  )
  const streamingMessage = computed(() =>
    currentSessionId.value ? (sessionStates.value[currentSessionId.value]?.streamingMessage ?? null) : null
  )

  function getSessionState(sessionId: string): SessionState {
    if (!sessionStates.value[sessionId]) {
      sessionStates.value[sessionId] = {
        messages: [],
        isStreaming: false,
        streamingMessage: null,
        loaded: false,
      }
    }
    return sessionStates.value[sessionId]
  }

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
    wsMap.get(id)?.disconnect()
    wsMap.delete(id)
    delete sessionStates.value[id]

    if (currentSessionId.value === id) {
      currentSessionId.value = null
      const first = sessions.value[0]
      if (first) {
        await switchSession(first.id)
      }
    }
  }

  async function switchSession(id: string) {
    if (currentSessionId.value === id) return
    currentSessionId.value = id

    const state = getSessionState(id)
    // 只有未加载过才从 API 拉取，已加载（包括正在流式中的）直接复用
    if (!state.loaded) {
      try {
        const data = await api.sessions.getMessages(id)
        state.messages = convertMessages(data.messages)
        state.loaded = true
      } catch (e) {
        console.error('加载消息失败', e)
      }
    }

    connectWS(id)
  }

  function convertMessages(rawMessages: Message[]): DisplayMessage[] {
    const result: DisplayMessage[] = []

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

  function flushStreamingMessage(sessionId: string) {
    const state = getSessionState(sessionId)
    if (
      state.streamingMessage &&
      (state.streamingMessage.content || (state.streamingMessage.toolCalls?.length ?? 0) > 0)
    ) {
      state.streamingMessage.isStreaming = false
      state.messages.push({ ...state.streamingMessage })
      state.streamingMessage = null
    } else {
      state.streamingMessage = null
    }
    state.isStreaming = false
  }

  function connectWS(sessionId: string) {
    const existing = wsMap.get(sessionId)
    if (existing?.isConnected) return

    const ws = new AgentWebSocket(sessionId)
    wsMap.set(sessionId, ws)

    ws.connect(
      (event) => handleStreamEvent(sessionId, event),
      () => {
        // WS 关闭时，将未完成的流式消息保存下来
        flushStreamingMessage(sessionId)
        wsMap.delete(sessionId)
      }
    ).catch((e) => console.error('WebSocket 连接失败', e))
  }

  function handleStreamEvent(sessionId: string, event: StreamEvent) {
    // 始终更新对应 session 的状态，不再因为非当前 session 而忽略事件
    const state = getSessionState(sessionId)

    if (event.type === 'content_delta') {
      if (!state.streamingMessage) {
        state.streamingMessage = {
          id: `streaming-${Date.now()}`,
          role: 'assistant',
          content: '',
          toolCalls: [],
          toolResults: {},
          isStreaming: true,
          timestamp: Date.now(),
        }
      }
      state.streamingMessage.content += event.content
    } else if (event.type === 'thinking') {
      if (!state.streamingMessage) {
        state.streamingMessage = {
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
      state.streamingMessage.reasoning = (state.streamingMessage.reasoning || '') + event.content
    } else if (event.type === 'tool_call') {
      if (!state.streamingMessage) {
        state.streamingMessage = {
          id: `streaming-${Date.now()}`,
          role: 'assistant',
          content: '',
          toolCalls: [],
          toolResults: {},
          isStreaming: true,
          timestamp: Date.now(),
        }
      }
      state.streamingMessage.toolCalls!.push({
        id: event.id,
        name: event.name,
        args: event.args,
      })
    } else if (event.type === 'tool_result') {
      if (state.streamingMessage?.toolCalls) {
        const tc = [...state.streamingMessage.toolCalls].reverse().find((t) => t.name === event.name)
        if (tc) {
          state.streamingMessage.toolResults![tc.id] = event.content
        }
      }
      if (TASK_TOOLS.has(event.name)) {
        tasksChangedAt.value++
      }
    } else if (event.type === 'done') {
      if (state.streamingMessage) {
        state.streamingMessage.isStreaming = false
        state.messages.push({ ...state.streamingMessage })
        state.streamingMessage = null
      }
      state.isStreaming = false
      loadSessions()
    } else if (event.type === 'error') {
      state.isStreaming = false
      state.streamingMessage = null
      console.error('Agent 错误:', event.message)
    } else if (event.type === 'session_title') {
      // 自动更新会话标题
      const session = sessions.value.find((s) => s.id === sessionId)
      if (session) {
        session.title = event.title
      }
    } else if (event.type === 'task_notification') {
      tasksChangedAt.value++
      lastTaskNotification.value = event
    }
  }

  async function sendMessage(content: string) {
    const sessionId = currentSessionId.value
    if (!sessionId) return

    const state = getSessionState(sessionId)
    if (state.isStreaming) return

    state.messages.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    })

    state.isStreaming = true
    state.streamingMessage = null

    let ws = wsMap.get(sessionId)
    if (!ws || !ws.isConnected) {
      ws = new AgentWebSocket(sessionId)
      wsMap.set(sessionId, ws)
      await ws.connect(
        (event) => handleStreamEvent(sessionId, event),
        () => {
          flushStreamingMessage(sessionId)
          wsMap.delete(sessionId)
        }
      )
    }
    ws.sendMessage(content)
  }

  function stopStreaming() {
    const sessionId = currentSessionId.value
    if (!sessionId) return
    const ws = wsMap.get(sessionId)
    ws?.stop()
    // 只更新 UI 状态，不清除 streamingMessage
    // 等待 backend 发送 done 事件后由 handleStreamEvent 统一处理内容保存
    getSessionState(sessionId).isStreaming = false
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
