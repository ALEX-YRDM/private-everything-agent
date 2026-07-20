import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 终端会话管理：一个抽屉、多个 tab，每个 tab 是一个独立的 pty。
 *
 * 每个 TerminalSession 只是"逻辑标识"，实际的 xterm 实例和 WebSocket 由
 * TerminalTabInstance 组件持有；组件用 :key="tab.id" 保持自己的生命周期。
 */

export interface TerminalSession {
  id: string       // 内部 id，例如 term-1，仅用于 v-for key
  title: string    // 标签显示名，默认 "终端 N"，用户可重命名
  cwd?: string     // 后端 ready 消息回填
  status: 'idle' | 'connecting' | 'connected' | 'closed'
}

export const useTerminalStore = defineStore('terminal', () => {
  const tabs = ref<TerminalSession[]>([])
  const activeId = ref<string | null>(null)
  let seq = 0

  const activeTab = computed<TerminalSession | null>(() => {
    if (!activeId.value) return null
    return tabs.value.find((t) => t.id === activeId.value) || null
  })

  function createTab(title?: string): TerminalSession {
    seq += 1
    const tab: TerminalSession = {
      id: `term-${Date.now()}-${seq}`,
      title: title ?? `终端 ${seq}`,
      status: 'idle',
    }
    tabs.value = [...tabs.value, tab]
    activeId.value = tab.id
    return tab
  }

  function closeTab(id: string) {
    const idx = tabs.value.findIndex((t) => t.id === id)
    if (idx < 0) return
    tabs.value.splice(idx, 1)
    if (activeId.value === id) {
      const next = tabs.value[Math.min(idx, tabs.value.length - 1)]
      activeId.value = next ? next.id : null
    }
  }

  function switchTab(id: string) {
    if (tabs.value.some((t) => t.id === id)) activeId.value = id
  }

  function renameTab(id: string, title: string) {
    const t = tabs.value.find((x) => x.id === id)
    if (t) t.title = title || t.title
  }

  function updateStatus(id: string, status: TerminalSession['status'], cwd?: string) {
    const t = tabs.value.find((x) => x.id === id)
    if (t) {
      t.status = status
      if (cwd !== undefined) t.cwd = cwd
    }
  }

  function closeAll() {
    tabs.value = []
    activeId.value = null
  }

  return {
    tabs, activeId, activeTab,
    createTab, closeTab, switchTab, renameTab, updateStatus, closeAll,
  }
})
