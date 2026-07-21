import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api/http'

export type TabKind = 'text' | 'image'

export interface CodeTab {
  path: string
  kind: TabKind
  /** 文本 tab：文件内容；图片 tab：留空（图片直接走 rawUrl） */
  content: string
  size: number
  truncated: boolean
  /** 图片 tab 用：img src；文本 tab 忽略 */
  rawUrl?: string
  /** 图片 tab 用：mime 类型 */
  mime?: string
  loading?: boolean
  error?: string
}

const MAX_TABS = 12

const IMAGE_EXTS = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico', '.avif',
])

function isImagePath(path: string): boolean {
  const dot = path.lastIndexOf('.')
  if (dot < 0) return false
  return IMAGE_EXTS.has(path.slice(dot).toLowerCase())
}

export const useCodeViewerStore = defineStore('codeViewer', () => {
  const open = ref(false)
  const tabs = ref<CodeTab[]>([])
  const activePath = ref<string | null>(null)

  const activeTab = computed<CodeTab | null>(() => {
    if (!activePath.value) return null
    return tabs.value.find((t) => t.path === activePath.value) || null
  })

  function showViewer() {
    open.value = true
  }
  function hideViewer() {
    open.value = false
  }
  function toggle() {
    open.value = !open.value
  }

  /** 打开文件；已开就切到那个 tab */
  async function openFile(sessionId: string, path: string) {
    // 打开面板
    open.value = true

    const existing = tabs.value.find((t) => t.path === path)
    if (existing) {
      activePath.value = path
      return
    }

    const isImage = isImagePath(path)

    // 塞一个 loading 占位
    const stub: CodeTab = {
      path,
      kind: isImage ? 'image' : 'text',
      content: '',
      size: 0,
      truncated: false,
      loading: true,
    }
    // 超过上限就顶掉最早未 active 的 tab
    if (tabs.value.length >= MAX_TABS) {
      const idx = tabs.value.findIndex((t) => t.path !== activePath.value)
      if (idx >= 0) tabs.value.splice(idx, 1)
    }
    tabs.value = [...tabs.value, stub]
    activePath.value = path

    try {
      if (isImage) {
        const meta = await api.sessions.getFileMeta(sessionId, path)
        const t = tabs.value.find((x) => x.path === path)
        if (t) {
          t.rawUrl = api.sessions.fileRawUrl(sessionId, path)
          t.size = meta.size
          t.mime = meta.mime
          t.loading = false
        }
      } else {
        const data = await api.sessions.getFileContent(sessionId, path)
        const t = tabs.value.find((x) => x.path === path)
        if (t) {
          t.content = data.content
          t.size = data.size
          t.truncated = data.truncated
          t.loading = false
        }
      }
    } catch (e: any) {
      const t = tabs.value.find((x) => x.path === path)
      if (t) {
        t.loading = false
        t.error = e?.message || String(e)
      }
    }
  }

  function closeTab(path: string) {
    const idx = tabs.value.findIndex((t) => t.path === path)
    if (idx < 0) return
    tabs.value.splice(idx, 1)
    if (activePath.value === path) {
      const next = tabs.value[Math.min(idx, tabs.value.length - 1)]
      activePath.value = next ? next.path : null
      if (!next) open.value = false
    }
  }

  function switchTab(path: string) {
    if (tabs.value.some((t) => t.path === path)) {
      activePath.value = path
    }
  }

  function closeAll() {
    tabs.value = []
    activePath.value = null
    open.value = false
  }

  return {
    open, tabs, activePath, activeTab,
    showViewer, hideViewer, toggle,
    openFile, closeTab, switchTab, closeAll,
  }
})
