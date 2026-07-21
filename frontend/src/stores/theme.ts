import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const LS_KEY = 'agent-theme-v1'
export type ThemeMode = 'light' | 'dark' | 'auto'

/**
 * 主题：light / dark / auto（跟随系统）。
 * - 全局效果：给 <html> 加 data-theme 属性；CSS 变量在 style.css 里按选择器切换
 * - Naive UI 效果：由 useThemeStore.naiveTheme 派生给 <NConfigProvider :theme>
 */
export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(loadMode())
  const systemPrefersDark = ref<boolean>(prefersDark())

  const effective = computed<'light' | 'dark'>(() =>
    mode.value === 'auto' ? (systemPrefersDark.value ? 'dark' : 'light') : mode.value,
  )

  // 首次同步 + 变更时更新 <html data-theme>
  applyToDom(effective.value)
  watch(effective, applyToDom)

  // 监听系统偏好变化（auto 模式下自动跟随）
  if (typeof window !== 'undefined' && window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => { systemPrefersDark.value = e.matches }
    if (mq.addEventListener) mq.addEventListener('change', handler)
    else mq.addListener?.(handler)
  }

  function setMode(v: ThemeMode) {
    mode.value = v
    try { localStorage.setItem(LS_KEY, v) } catch { /* ignore */ }
  }

  function cycle() {
    const next: Record<ThemeMode, ThemeMode> = {
      light: 'dark',
      dark: 'auto',
      auto: 'light',
    }
    setMode(next[mode.value])
  }

  return { mode, effective, setMode, cycle }
})

function loadMode(): ThemeMode {
  try {
    const v = localStorage.getItem(LS_KEY) as ThemeMode | null
    if (v === 'light' || v === 'dark' || v === 'auto') return v
  } catch { /* ignore */ }
  return 'auto'
}

function prefersDark(): boolean {
  return typeof window !== 'undefined'
    && window.matchMedia
    && window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyToDom(theme: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', theme)
  document.documentElement.style.colorScheme = theme
}
