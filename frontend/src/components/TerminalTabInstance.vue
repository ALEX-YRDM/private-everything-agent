<script setup lang="ts">
/**
 * 单个终端 tab 实例：xterm.js ↔ WebSocket ↔ Unix PTY。
 *
 * 组件用 :key="tab.id" 保持生命周期 —— 切 tab 时 v-show 隐藏而非销毁，
 * 后台 tab 的 shell 状态仍在运行，输出会积压在 xterm 缓冲区里。
 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { Terminal } from 'xterm'
import { FitAddon } from '@xterm/addon-fit'
import 'xterm/css/xterm.css'
import { useChatStore } from '../stores/chat'
import { useTerminalStore, type TerminalSession } from '../stores/terminal'

const props = defineProps<{
  tab: TerminalSession
  active: boolean  // 当前是否被选中（用于 fit 触发）
}>()

const chat = useChatStore()
const store = useTerminalStore()

const termHost = ref<HTMLDivElement | null>(null)

let term: Terminal | null = null
let fit: FitAddon | null = null
let ws: WebSocket | null = null
let resizeObserver: ResizeObserver | null = null

function wsUrl(sid: string): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/api/ws/terminal/${encodeURIComponent(sid)}`
}

function initTerm() {
  if (term || !termHost.value) return
  term = new Terminal({
    cursorBlink: true,
    fontSize: 12.5,
    fontFamily: 'SF Mono, Monaco, Cascadia Code, Menlo, Consolas, monospace',
    lineHeight: 1.2,
    scrollback: 5000,
    convertEol: false,
    allowProposedApi: true,
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#d4d4d4',
      selectionBackground: 'rgba(22, 119, 255, 0.35)',
      black: '#000000', red: '#f78166', green: '#56d364', yellow: '#e3b341',
      blue: '#79c0ff', magenta: '#d2a8ff', cyan: '#39c5cf', white: '#d4d4d4',
      brightBlack: '#6b7280', brightRed: '#ff8a76', brightGreen: '#7ee787',
      brightYellow: '#f0d370', brightBlue: '#a5d6ff', brightMagenta: '#d2a8ff',
      brightCyan: '#56d4dd', brightWhite: '#ffffff',
    },
  })
  fit = new FitAddon()
  term.loadAddon(fit)
  term.open(termHost.value)
  try { fit.fit() } catch { /* ignore */ }

  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }))
    }
  })

  term.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', cols, rows }))
    }
  })

  // 容器尺寸变化 → 重新 fit
  resizeObserver = new ResizeObserver(() => {
    try { fit?.fit() } catch { /* ignore */ }
  })
  resizeObserver.observe(termHost.value)
}

function connect() {
  const sid = chat.currentSessionId
  if (!sid) return
  if (ws && ws.readyState <= WebSocket.OPEN) {
    try { ws.close() } catch { /* ignore */ }
  }
  store.updateStatus(props.tab.id, 'connecting')
  ws = new WebSocket(wsUrl(sid))
  ws.onopen = () => {
    store.updateStatus(props.tab.id, 'connected')
    if (term) {
      const { cols, rows } = term
      ws?.send(JSON.stringify({ type: 'resize', cols, rows }))
    }
  }
  ws.onmessage = (ev) => {
    let obj: any
    try { obj = JSON.parse(ev.data) } catch { return }
    if (obj.type === 'output') {
      term?.write(obj.data)
    } else if (obj.type === 'ready') {
      store.updateStatus(props.tab.id, 'connected', obj.cwd)
    } else if (obj.type === 'exit') {
      term?.writeln(`\r\n\x1b[90m[已退出，code=${obj.code}]\x1b[0m`)
      store.updateStatus(props.tab.id, 'closed')
    }
  }
  ws.onerror = () => store.updateStatus(props.tab.id, 'closed')
  ws.onclose = () => {
    if (props.tab.status !== 'closed') store.updateStatus(props.tab.id, 'closed')
  }
}

function reconnect() {
  term?.clear()
  connect()
}
function sendCtrlC() {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'input', data: '' }))
}
function clearScreen() { term?.clear() }

// 切到本 tab 时 → 重算尺寸并聚焦
watch(() => props.active, (v) => {
  if (v) {
    requestAnimationFrame(() => {
      try { fit?.fit() } catch { /* ignore */ }
      try { term?.focus() } catch { /* ignore */ }
    })
  }
})

onMounted(() => {
  initTerm()
  // 无论是否绑定 working_dir 都尝试连接；后端会 fallback 到默认 workspace
  if (chat.currentSessionId) connect()
  else store.updateStatus(props.tab.id, 'idle')
})

onBeforeUnmount(() => {
  try { ws?.close() } catch { /* ignore */ }
  try { resizeObserver?.disconnect() } catch { /* ignore */ }
  try { term?.dispose() } catch { /* ignore */ }
  ws = null
  term = null
  fit = null
})

defineExpose({ reconnect, sendCtrlC, clearScreen })
</script>

<template>
  <div class="tab-instance" v-show="active">
    <div class="ti-host" ref="termHost" />
  </div>
</template>

<style scoped>
.tab-instance {
  flex: 1;
  min-height: 0;
  display: flex;
}
.ti-host {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 4px 8px 6px;
  background: #1e1e1e;
}
.ti-host :deep(.xterm),
.ti-host :deep(.xterm-viewport),
.ti-host :deep(.xterm-screen) {
  height: 100% !important;
}
</style>
