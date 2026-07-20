import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const LS_KEY = 'agent-layout-v1'

interface Persisted {
  leftWidth: number
  rightWidth: number
  leftCollapsed: boolean
  rightCollapsed: boolean
  terminalWidth: number
  terminalOpen: boolean
}

const DEFAULTS: Persisted = {
  leftWidth: 240,
  rightWidth: 280,
  leftCollapsed: false,
  rightCollapsed: false,
  terminalWidth: 560,
  terminalOpen: false,
}

export const LEFT_MIN = 180
export const LEFT_MAX = 480
export const RIGHT_MIN = 220
export const RIGHT_MAX = 560
export const COLLAPSED_WIDTH = 32
export const TERM_MIN = 320
export const TERM_MAX = 1200

function load(): Persisted {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return { ...DEFAULTS }
    const p = JSON.parse(raw) as Partial<Persisted>
    return {
      leftWidth: clamp(p.leftWidth ?? DEFAULTS.leftWidth, LEFT_MIN, LEFT_MAX),
      rightWidth: clamp(p.rightWidth ?? DEFAULTS.rightWidth, RIGHT_MIN, RIGHT_MAX),
      leftCollapsed: !!p.leftCollapsed,
      rightCollapsed: !!p.rightCollapsed,
      terminalWidth: clamp(p.terminalWidth ?? DEFAULTS.terminalWidth, TERM_MIN, TERM_MAX),
      terminalOpen: !!p.terminalOpen,
    }
  } catch {
    return { ...DEFAULTS }
  }
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v))
}

export const useLayoutStore = defineStore('layout', () => {
  const initial = load()
  const leftWidth = ref(initial.leftWidth)
  const rightWidth = ref(initial.rightWidth)
  const leftCollapsed = ref(initial.leftCollapsed)
  const rightCollapsed = ref(initial.rightCollapsed)
  const terminalWidth = ref(initial.terminalWidth)
  const terminalOpen = ref(initial.terminalOpen)

  function persist() {
    try {
      localStorage.setItem(
        LS_KEY,
        JSON.stringify({
          leftWidth: leftWidth.value,
          rightWidth: rightWidth.value,
          leftCollapsed: leftCollapsed.value,
          rightCollapsed: rightCollapsed.value,
          terminalWidth: terminalWidth.value,
          terminalOpen: terminalOpen.value,
        } as Persisted),
      )
    } catch {}
  }

  watch([leftWidth, rightWidth, leftCollapsed, rightCollapsed, terminalWidth, terminalOpen], persist)

  function setLeftWidth(w: number) { leftWidth.value = clamp(w, LEFT_MIN, LEFT_MAX) }
  function setRightWidth(w: number) { rightWidth.value = clamp(w, RIGHT_MIN, RIGHT_MAX) }
  function setTerminalWidth(w: number) { terminalWidth.value = clamp(w, TERM_MIN, TERM_MAX) }
  function toggleLeft() { leftCollapsed.value = !leftCollapsed.value }
  function toggleRight() { rightCollapsed.value = !rightCollapsed.value }
  function toggleTerminal() { terminalOpen.value = !terminalOpen.value }

  return {
    leftWidth, rightWidth, leftCollapsed, rightCollapsed,
    terminalWidth, terminalOpen,
    setLeftWidth, setRightWidth, setTerminalWidth,
    toggleLeft, toggleRight, toggleTerminal,
  }
})
