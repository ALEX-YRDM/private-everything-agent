export type SubAgentInnerEvent =
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; name: string; id: string; args: Record<string, unknown> }
  | { type: 'tool_call_delta'; id: string; args_delta: string }
  | { type: 'tool_result'; id?: string; name: string; content: string }
  | { type: 'content_delta'; content: string }
  | { type: 'done'; content: string }
  | { type: 'error'; message: string }

export type ConfirmPreview =
  | { kind: 'exec'; command: string; cwd: string }
  | { kind: 'file'; path: string }
  | { kind: 'patch'; patch: string }

export interface TodoItem {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

export type StreamEvent =
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; name: string; id: string; args: Record<string, unknown> }
  | { type: 'tool_result'; id?: string; name: string; content: string }
  | { type: 'content_delta'; content: string }
  | { type: 'done'; content: string; input_tokens?: number | null; output_tokens?: number | null }
  | { type: 'error'; message: string; category?: string; retriable?: boolean; hint?: string }
  | { type: 'session_title'; title: string; session_id?: string }
  | { type: 'task_notification'; task_id: number; task_name: string; status: 'success' | 'error'; session_id: string | null; message: string }
  | { type: 'tool_call_delta'; id: string; args_delta: string }
  | { type: 'subagent_start'; subagent_id: string; session_id: string; task: string }
  | { type: 'subagent_event'; subagent_id: string; event: SubAgentInnerEvent }
  | { type: 'subagent_done'; subagent_id: string; result: string; error?: string }
  | { type: 'tool_confirm'; id: string; name: string; args: Record<string, unknown>; cwd: string; why: string; preview?: ConfirmPreview; suggested_trust_path?: string; suggested_trust_command?: string }
  | { type: 'tool_denied'; id: string; name: string; reason: string }
  | { type: 'todos_update'; session_id?: string; todos: TodoItem[] }
  | { type: 'plan_mode_update'; session_id?: string; plan_mode: boolean; reason?: string | null }

export type ConfirmDecision = 'allow' | 'deny' | 'trust_path' | 'trust_command'

const WS_BASE = import.meta.env.VITE_WS_BASE || 'ws://localhost:8000'

export class AgentWebSocket {
  private ws: WebSocket | null = null
  private sessionId: string
  private onEventCb: ((event: StreamEvent) => void) | null = null
  private onCloseCb: (() => void) | null = null

  constructor(sessionId: string) {
    this.sessionId = sessionId
  }

  connect(onEvent: (event: StreamEvent) => void, onClose?: () => void): Promise<void> {
    this.onEventCb = onEvent
    this.onCloseCb = onClose || null
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${WS_BASE}/ws/${this.sessionId}`)
      this.ws.onopen = () => resolve()
      this.ws.onerror = (e) => reject(e)
      this.ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data) as StreamEvent
          this.onEventCb?.(event)
        } catch {
          // ignore parse errors
        }
      }
      this.ws.onclose = () => this.onCloseCb?.()
    })
  }

  sendMessage(content: string, images?: string[], files?: Array<{name: string; mime_type: string; content: string; size?: number}>): void {
    const msg: Record<string, unknown> = { type: 'message', content }
    if (images?.length) msg.images = images
    if (files?.length) msg.files = files
    this.ws?.send(JSON.stringify(msg))
  }

  sendConfirmResponse(id: string, decision: ConfirmDecision, extra?: string): void {
    this.ws?.send(JSON.stringify({
      type: 'tool_confirm_response',
      id,
      decision,
      extra,
    }))
  }

  stop(): void {
    this.ws?.send(JSON.stringify({ type: 'stop' }))
  }

  disconnect(): void {
    this.ws?.close()
    this.ws = null
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
