import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api, type Session, type Message } from '../api/http'
import { AgentWebSocket, type StreamEvent, type SubAgentInnerEvent, type ConfirmDecision, type ConfirmPreview } from '../api/websocket'

export interface SubAgentState {
  id: string
  session_id: string
  task: string
  status: 'running' | 'completed' | 'failed'
  events: SubAgentInnerEvent[]
  result?: string
  error?: string
}

export interface PendingConfirm {
  id: string             // tool_call_id
  session_id: string
  name: string
  args: Record<string, unknown>
  cwd: string
  why: string
  preview?: ConfirmPreview
  suggested_trust_path?: string
  suggested_trust_command?: string
  ts: number
}

export interface FileAttachment {
  name: string
  mime_type: string
  parsed_content?: string
  size?: number
}

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'error'
  content: string
  images?: string[]          // base64 data URL 图片列表（用户消息附图）
  files?: FileAttachment[]   // 文件附件列表
  attachedPaths?: string[]   // 用户消息发送时携带的 @ 引用路径（只读展示）
  reasoning?: string
  toolCalls?: ToolCallDisplay[]
  toolResults?: Record<string, string>
  subAgents?: SubAgentState[]
  isStreaming?: boolean
  inputTokens?: number
  outputTokens?: number
  errorCategory?: string     // 错误分类（error role 专用）
  errorHint?: string         // 错误建议（error role 专用）
  timestamp: number
}

export interface ToolCallDisplay {
  id: string
  name: string
  args: Record<string, unknown>
  streamingArgs?: string  // LLM 流式生成参数时的原始文本（参数生成完毕后清空）
}

interface SessionState {
  messages: DisplayMessage[]
  isStreaming: boolean
  streamingMessage: DisplayMessage | null
  loaded: boolean
  // 当前消息轮次中活跃的 SubAgent（streaming 期间）
  activeSubAgents: Map<string, SubAgentState>
  // 已展开的 SubAgent session 列表（用于 SessionList）
  subagentSessions: Session[]
  subagentSessionsLoaded: boolean
  // 破坏性工具确认请求（tool_call_id → payload）
  pendingConfirms: Map<string, PendingConfirm>
  // 附加到"下一条消息"的文件路径列表（发送后清空；切会话不共享）
  pendingAttachments: string[]
}

const TASK_TOOLS = new Set(['create_task', 'delete_task', 'update_task'])

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const sessionStates = ref<Record<string, SessionState>>({})
  const wsMap = new Map<string, AgentWebSocket>()

  /**
   * WS LRU 保留策略：最多保留 WS_KEEP_ALIVE 条活连接，
   * 保证"后台任务通知"仍然可到达最近使用的会话；超出的老连接主动 close。
   * 切回旧会话时 sendMessage/connectWS 会 lazy 重连。
   */
  const WS_KEEP_ALIVE = 3
  const wsAccessOrder: string[] = []  // 最近 → 最早

  function touchWs(sessionId: string) {
    const idx = wsAccessOrder.indexOf(sessionId)
    if (idx >= 0) wsAccessOrder.splice(idx, 1)
    wsAccessOrder.unshift(sessionId)
    while (wsAccessOrder.length > WS_KEEP_ALIVE) {
      const evict = wsAccessOrder.pop()!
      if (evict === sessionId) continue
      const w = wsMap.get(evict)
      if (w) {
        try { w.disconnect() } catch { /* ignore */ }
        wsMap.delete(evict)
      }
    }
  }

  function forgetWs(sessionId: string) {
    const idx = wsAccessOrder.indexOf(sessionId)
    if (idx >= 0) wsAccessOrder.splice(idx, 1)
  }

  /** 每当任务工具执行完毕，此计数器 +1，供 SchedulerPanel 监听刷新。 */
  const tasksChangedAt = ref(0)
  /** 最近一次收到的定时任务广播通知（App.vue 监听并显示 toast）。 */
  const lastTaskNotification = ref<{ task_name: string; status: string; message: string } | null>(null)
  /** 最近一次 Agent 流式错误（App.vue 监听并弹出 toast）。 */
  const lastError = ref<{ session_id: string; message: string; at: number } | null>(null)
  /** 请求向当前会话输入框追加文本（文件树点击文件时使用，ChatPanel watch）。 */
  const pendingInsert = ref<{ text: string; at: number } | null>(null)

  function requestInsertToInput(text: string) {
    pendingInsert.value = { text, at: Date.now() }
  }

  const currentSession = computed(() =>
    sessions.value.find((s) => s.id === currentSessionId.value) || null
  )

  // 当前会话的 pendingAttachments（响应式）
  const pendingAttachments = computed(() =>
    currentSessionId.value
      ? (sessionStates.value[currentSessionId.value]?.pendingAttachments ?? [])
      : [],
  )

  /** 加入附件；重复路径不再加（去重）。返回是否真的加入了。 */
  function addAttachment(path: string): boolean {
    const sid = currentSessionId.value
    if (!sid) return false
    const state = getSessionState(sid)
    if (state.pendingAttachments.includes(path)) return false
    state.pendingAttachments = [...state.pendingAttachments, path]
    return true
  }

  function removeAttachment(path: string) {
    const sid = currentSessionId.value
    if (!sid) return
    const state = getSessionState(sid)
    state.pendingAttachments = state.pendingAttachments.filter((p) => p !== path)
  }

  function clearAttachments(sessionId?: string) {
    const sid = sessionId ?? currentSessionId.value
    if (!sid) return
    const state = getSessionState(sid)
    state.pendingAttachments = []
  }

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
        activeSubAgents: new Map(),
        subagentSessions: [],
        subagentSessionsLoaded: false,
        pendingConfirms: new Map(),
        pendingAttachments: [],
      }
    }
    return sessionStates.value[sessionId]!
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
    forgetWs(id)
    delete sessionStates.value[id]

    if (currentSessionId.value === id) {
      currentSessionId.value = null
      const first = sessions.value[0]
      if (first) {
        await switchSession(first.id)
      }
    }
  }

  /** 检查某个 session 是否是当前正在执行的 SubAgent 子会话 */
  function getRunningSubAgent(subSessionId: string): SubAgentState | undefined {
    for (const st of Object.values(sessionStates.value)) {
      for (const sa of st.activeSubAgents.values()) {
        if (sa.session_id === subSessionId && sa.status === 'running') return sa
      }
    }
    return undefined
  }

  async function switchSession(id: string) {
    if (currentSessionId.value === id) return
    currentSessionId.value = id
    // 提前占位：即使还没建 WS，也保证 LRU 把当前会话放到最近位置
    touchWs(id)

    const state = getSessionState(id)
    // 只有未加载过才从 API 拉取，已加载（包括正在流式中的）直接复用
    if (!state.loaded) {
      try {
        const data = await api.sessions.getMessages(id)
        state.messages = convertMessages(data.messages)
        // 若该会话是正在运行的子任务且 DB 中还没消息（save_turn 未完成），
        // 不标记 loaded=true，留给 subagent_done 自动刷新
        const isRunningEmpty = data.messages.length === 0 && getRunningSubAgent(id) !== undefined
        if (!isRunningEmpty) {
          state.loaded = true
        }
      } catch (e) {
        console.error('加载消息失败', e)
      }
    }

    connectWS(id)
  }

  function convertMessages(rawMessages: Message[]): DisplayMessage[] {
    const result: DisplayMessage[] = []
    // 当前正在积累的 assistant 轮次（一轮 = 多次 LLM 调用 + 工具结果，直到下一条 user 消息）
    let pendingAssistant: DisplayMessage | null = null

    function flushAssistant() {
      if (pendingAssistant) {
        // 修整：无 toolCalls 时清除空 toolResults
        if (!pendingAssistant.toolCalls?.length) pendingAssistant.toolResults = undefined
        result.push(pendingAssistant)
        pendingAssistant = null
      }
    }

    for (const m of rawMessages) {
      if (m.role === 'user') {
        flushAssistant()
        let textContent = m.content || ''
        let images: string[] | undefined
        let files: FileAttachment[] | undefined

        if (textContent.startsWith('[')) {
          try {
            const parts = JSON.parse(textContent) as Array<{ type: string; text?: string; image_url?: { url: string } }>
            textContent = parts.filter(p => p.type === 'text').map(p => p.text || '').join('\n')
            images = parts.filter(p => p.type === 'image_url' && p.image_url?.url).map(p => p.image_url!.url)
            if (!images.length) images = undefined
          } catch {}
        }

        if (m.files) {
          try {
            files = JSON.parse(m.files) as FileAttachment[]
            if (!files.length) files = undefined
          } catch {}
        }

        result.push({
          id: `msg-${m.id}`,
          role: 'user',
          content: textContent,
          images,
          files,
          timestamp: new Date(m.created_at).getTime(),
        })
      } else if (m.role === 'assistant') {
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
        if (!pendingAssistant) {
          // 开始新的 assistant 轮次
          pendingAssistant = {
            id: `msg-${m.id}`,
            role: 'assistant',
            content: m.content || '',
            reasoning: m.reasoning || undefined,
            toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
            toolResults: {},
            inputTokens: m.input_tokens ?? undefined,
            outputTokens: m.output_tokens ?? undefined,
            timestamp: new Date(m.created_at).getTime(),
          }
        } else {
          // 同一轮：追加 toolCalls、更新 reasoning 和 content（用最新非空值）
          if (toolCalls.length > 0) {
            pendingAssistant.toolCalls = [...(pendingAssistant.toolCalls ?? []), ...toolCalls]
          }
          if (m.reasoning) {
            pendingAssistant.reasoning = (pendingAssistant.reasoning ?? '') + m.reasoning
          }
          if (m.content) pendingAssistant.content = m.content
          // 最终 assistant 消息的 token 数最准确，优先覆盖
          if (m.input_tokens != null) pendingAssistant.inputTokens = m.input_tokens
          if (m.output_tokens != null) pendingAssistant.outputTokens = m.output_tokens
        }
      } else if (m.role === 'tool' && m.tool_call_id) {
        if (pendingAssistant) {
          if (!pendingAssistant.toolResults) pendingAssistant.toolResults = {}
          pendingAssistant.toolResults[m.tool_call_id] = m.content || ''
        }
      }
    }

    flushAssistant()
    return result
  }

  function flushStreamingMessage(sessionId: string) {
    const state = getSessionState(sessionId)
    if (
      state.streamingMessage &&
      (state.streamingMessage.content ||
        (state.streamingMessage.toolCalls?.length ?? 0) > 0 ||
        (state.streamingMessage.subAgents?.length ?? 0) > 0)
    ) {
      state.streamingMessage.isStreaming = false
      state.messages.push({ ...state.streamingMessage })
      state.streamingMessage = null
    } else {
      state.streamingMessage = null
    }
    state.activeSubAgents.clear()
    state.isStreaming = false
  }

  function connectWS(sessionId: string) {
    const existing = wsMap.get(sessionId)
    if (existing?.isConnected) {
      touchWs(sessionId)
      return
    }

    const ws = new AgentWebSocket(sessionId)
    wsMap.set(sessionId, ws)
    touchWs(sessionId)

    ws.connect(
      (event) => handleStreamEvent(sessionId, event),
      () => {
        // WS 关闭时，将未完成的流式消息保存下来
        flushStreamingMessage(sessionId)
        wsMap.delete(sessionId)
        forgetWs(sessionId)
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
      // 若已存在同 id 的条目（早期空参数占位），则更新参数并清空流式文本；否则新增
      const existing = state.streamingMessage.toolCalls!.find(t => t.id === event.id)
      if (existing) {
        existing.args = event.args
        existing.streamingArgs = undefined  // 参数生成完毕，清空流式文本
      } else {
        state.streamingMessage.toolCalls!.push({
          id: event.id,
          name: event.name,
          args: event.args,
        })
      }
    } else if (event.type === 'tool_call_delta') {
      // 追加参数增量到流式文本，让用户实时看到参数内容
      const tc = state.streamingMessage?.toolCalls?.find(t => t.id === event.id)
      if (tc) {
        tc.streamingArgs = (tc.streamingArgs ?? '') + event.args_delta
      }
    } else if (event.type === 'tool_result') {
      if (state.streamingMessage?.toolCalls) {
        // 优先按 tool_call_id 精确匹配（后端已在 tool_result 事件中携带 id 字段）
        const tcById = event.id
          ? state.streamingMessage.toolCalls.find((t) => t.id === event.id)
          : undefined
        // 兜底：按 name 反向查找尚未有结果的 tool_call（兼容旧后端不携带 id 的情况）
        const tc = tcById
          ?? [...state.streamingMessage.toolCalls].reverse().find(
              (t) => t.name === event.name && !state.streamingMessage!.toolResults![t.id]
            )
        if (tc) {
          state.streamingMessage.toolResults![tc.id] = event.content
        }
      }
      if (TASK_TOOLS.has(event.name)) {
        tasksChangedAt.value++
      }
    } else if (event.type === 'subagent_start') {
      const sa: SubAgentState = {
        id: event.subagent_id,
        session_id: event.session_id,
        task: event.task,
        status: 'running',
        events: [],
      }
      state.activeSubAgents.set(event.subagent_id, sa)
      // 确保 streamingMessage 存在并附加 SubAgent
      if (!state.streamingMessage) {
        state.streamingMessage = {
          id: `streaming-${Date.now()}`,
          role: 'assistant',
          content: '',
          toolCalls: [],
          toolResults: {},
          subAgents: [],
          isStreaming: true,
          timestamp: Date.now(),
        }
      }
      if (!state.streamingMessage.subAgents) {
        state.streamingMessage.subAgents = []
      }
      state.streamingMessage.subAgents.push(sa)
    } else if (event.type === 'subagent_event') {
      // 从响应式数组中查找 sa，确保触发 Vue 响应式更新
      const sa = state.streamingMessage?.subAgents?.find(s => s.id === event.subagent_id)
      if (sa) {
        const inner = event.event
        // tool_call 事件：若同 id 已存在则就地更新（避免 early空参 和 full参 重复显示）
        if (inner.type === 'tool_call') {
          const existingIdx = sa.events.findIndex(
            e => e.type === 'tool_call' && (e as typeof inner).id === inner.id
          )
          if (existingIdx >= 0) {
            sa.events[existingIdx] = inner
          } else {
            sa.events.push(inner)
          }
        } else {
          sa.events.push(inner)
        }
      }
    } else if (event.type === 'subagent_done') {
      // 从响应式数组中查找 sa，确保触发 Vue 响应式更新
      const sa = state.streamingMessage?.subAgents?.find(s => s.id === event.subagent_id)
      if (sa) {
        sa.status = event.error ? 'failed' : 'completed'
        sa.result = event.result
        sa.error = event.error
        // 重置该子会话的加载状态，确保下次点击能重新拉取已保存的消息
        if (sa.session_id) {
          const subSt = sessionStates.value[sa.session_id]
          if (subSt) {
            subSt.loaded = false
          }
          // 若用户当前正在查看该子会话，立即重新加载消息
          if (currentSessionId.value === sa.session_id) {
            api.sessions.getMessages(sa.session_id).then((data) => {
              const subState = getSessionState(sa.session_id)
              subState.messages = convertMessages(data.messages)
              subState.loaded = true
            }).catch(() => {})
          }
        }
      }
      // 同步更新 activeSubAgents（用于兜底）
      const saMap = state.activeSubAgents.get(event.subagent_id)
      if (saMap && !state.streamingMessage?.subAgents?.find(s => s.id === event.subagent_id)) {
        saMap.status = event.error ? 'failed' : 'completed'
        saMap.result = event.result
        saMap.error = event.error
      }
    } else if (event.type === 'done') {
      if (state.streamingMessage) {
        state.streamingMessage.isStreaming = false
        if (event.input_tokens != null) state.streamingMessage.inputTokens = event.input_tokens
        if (event.output_tokens != null) state.streamingMessage.outputTokens = event.output_tokens
        state.messages.push({ ...state.streamingMessage })
        state.streamingMessage = null
      }
      state.activeSubAgents.clear()
      state.isStreaming = false
      // 重置子会话缓存，使 ⚙ 按钮下次展开时能拉取最新子会话列表
      state.subagentSessionsLoaded = false
      loadSessions()
    } else if (event.type === 'tool_confirm') {
      state.pendingConfirms.set(event.id, {
        id: event.id,
        session_id: sessionId,
        name: event.name,
        args: event.args,
        cwd: event.cwd,
        why: event.why,
        preview: event.preview,
        suggested_trust_path: event.suggested_trust_path,
        suggested_trust_command: event.suggested_trust_command,
        ts: Date.now(),
      })
    } else if (event.type === 'tool_denied') {
      state.pendingConfirms.delete(event.id)
      // 标记流式消息中对应工具调用为拒绝状态（tool_result 会紧跟着到，直接由现有逻辑写入结果）
    } else if (event.type === 'error') {
      // 1) 如果有正在流式的 assistant 消息，把已生成的内容固化进消息列表
      if (state.streamingMessage) {
        state.streamingMessage.isStreaming = false
        if (
          state.streamingMessage.content ||
          (state.streamingMessage.toolCalls?.length ?? 0) > 0 ||
          (state.streamingMessage.subAgents?.length ?? 0) > 0
        ) {
          state.messages.push({ ...state.streamingMessage })
        }
        state.streamingMessage = null
      }
      // 2) 把错误作为一条 error 消息气泡插入对话流，让用户在历史中看得到
      state.messages.push({
        id: `error-${Date.now()}`,
        role: 'error',
        content: event.message || '未知错误',
        errorCategory: event.category,
        errorHint: event.hint,
        timestamp: Date.now(),
      })
      state.activeSubAgents.clear()
      state.isStreaming = false
      // 3) 触发顶层 toast 通知（TOOL_PERMISSION_DENIED 是用户自己拒绝的，不弹）
      if (event.category !== 'TOOL_PERMISSION_DENIED') {
        lastError.value = {
          session_id: sessionId,
          message: event.hint || event.message || '未知错误',
          at: Date.now(),
        }
      }
      console.error('Agent 错误:', event.category, event.message)
    } else if (event.type === 'session_title') {
      // 用事件携带的 session_id 精确匹配（后台广播场景），fallback 到当前 WS 的 sessionId
      const targetId = event.session_id || sessionId
      const session = sessions.value.find((s) => s.id === targetId)
      if (session) {
        session.title = event.title
      }
    } else if (event.type === 'task_notification') {
      tasksChangedAt.value++
      lastTaskNotification.value = event
    }
  }

  async function sendMessage(content: string, images?: string[], files?: Array<{name: string; mime_type: string; content: string; size?: number}>) {
    const sessionId = currentSessionId.value
    if (!sessionId) return

    const state = getSessionState(sessionId)
    if (state.isStreaming) return

    // 消费 pendingAttachments：拼到 content 尾部让 Agent 感知，同时留一份在气泡上展示
    const attached = state.pendingAttachments.slice()
    let outgoingContent = content
    if (attached.length) {
      const list = attached.map((p) => `- ${p}`).join('\n')
      outgoingContent = content
        ? `${content}\n\n[本条附加了以下文件（相对当前 cwd）：]\n${list}`
        : `[本条附加了以下文件（相对当前 cwd）：]\n${list}`
    }

    state.messages.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content,   // 气泡里只显示用户手写的部分
      images: images?.length ? images : undefined,
      files: files?.length ? files.map(f => ({ name: f.name, mime_type: f.mime_type, size: f.size })) : undefined,
      attachedPaths: attached.length ? attached : undefined,
      timestamp: Date.now(),
    })

    // 清空 pendingAttachments（发一次消费一次）
    state.pendingAttachments = []

    state.isStreaming = true
    state.streamingMessage = null

    let ws = wsMap.get(sessionId)
    if (!ws || !ws.isConnected) {
      ws = new AgentWebSocket(sessionId)
      wsMap.set(sessionId, ws)
      touchWs(sessionId)
      await ws.connect(
        (event) => handleStreamEvent(sessionId, event),
        () => {
          flushStreamingMessage(sessionId)
          wsMap.delete(sessionId)
          forgetWs(sessionId)
        }
      )
    }
    ws.sendMessage(outgoingContent, images, files)
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

  /** 回复破坏性工具的确认请求（allow / deny / trust_path / trust_command）。 */
  function sendConfirmResponse(sessionId: string, id: string, decision: ConfirmDecision, extra?: string) {
    const ws = wsMap.get(sessionId)
    if (!ws?.isConnected) return
    ws.sendConfirmResponse(id, decision, extra)
    // 从 pendingConfirms 移除（后端会在 tool_result 后返回，但 UI 立即隐藏）
    getSessionState(sessionId).pendingConfirms.delete(id)
  }

  async function renameSession(id: string, title: string) {
    await api.sessions.updateTitle(id, title)
    const s = sessions.value.find((s) => s.id === id)
    if (s) s.title = title
  }

  async function loadSubagentSessions(sessionId: string) {
    const state = getSessionState(sessionId)
    if (state.subagentSessionsLoaded) return
    try {
      const data = await api.sessions.getSubagentSessions(sessionId)
      state.subagentSessions = data.sessions
      state.subagentSessionsLoaded = true
    } catch (e) {
      console.error('加载子 Agent 会话失败', e)
    }
  }

  function getSubagentSessions(sessionId: string): Session[] {
    return sessionStates.value[sessionId]?.subagentSessions ?? []
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
    lastError,
    pendingInsert,
    pendingAttachments,
    addAttachment,
    removeAttachment,
    clearAttachments,
    requestInsertToInput,
    init,
    loadSessions,
    createSession,
    deleteSession,
    switchSession,
    sendMessage,
    stopStreaming,
    sendConfirmResponse,
    renameSession,
    loadSubagentSessions,
    getSubagentSessions,
    getSessionState,
    getRunningSubAgent,
  }
})
