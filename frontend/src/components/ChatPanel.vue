<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted, inject } from 'vue'
import {
  NInput, NButton, NScrollbar, NSpin, NEmpty, NTooltip,
  NPopover, NDivider, NSwitch, NTag, NSelect,
  useMessage,
} from 'naive-ui'
import MessageBubble from './MessageBubble.vue'
import SubAgentBlock from './SubAgentBlock.vue'
import ToolConfirmDialog from './ToolConfirmDialog.vue'
import WorkingDirPicker from './WorkingDirPicker.vue'
import MentionPopover, { type MentionCandidate } from './MentionPopover.vue'
import { useChatStore } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'
import { api, type PromptTemplate, type ToolState } from '../api/http'
import type { ConfirmDecision } from '../api/websocket'

// App.vue provide 的三个动作
const openScheduler = inject<() => void>('openScheduler', () => {})
const openSettings = inject<() => void>('openSettings', () => {})
const toggleTerminal = inject<() => void>('toggleTerminal', () => {})

const chat = useChatStore()
const settings = useSettingsStore()
const message = useMessage()
const inputText = ref('')
const scrollbarRef = ref<InstanceType<typeof NScrollbar> | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

// ── 图片附件 ─────────────────────────────────────────────────────────────────
const MAX_IMAGE_SIZE = 10 * 1024 * 1024  // 10 MB
const MAX_IMAGE_LONG_EDGE = 1024         // 长边超过则等比缩放到此值
const attachedImages = ref<string[]>([])

// ── 文件附件 ─────────────────────────────────────────────────────────────────
const MAX_FILE_SIZE = 10 * 1024 * 1024  // 10 MB
const SUPPORTED_FILE_EXTENSIONS = new Set([
  'txt', 'md', 'markdown', 'json', 'csv', 'yaml', 'yml',
  'py', 'js', 'ts', 'tsx', 'jsx', 'java', 'cpp', 'c', 'h', 'go', 'rs', 'rb', 'php', 'sql', 'sh', 'bash', 'dockerfile', 'xml', 'html', 'css',
  'docx', 'xlsx'
])
interface AttachedFile {
  name: string
  size: number
  content: string  // base64
}
const attachedFiles = ref<AttachedFile[]>([])
const fileInputRef2 = ref<HTMLInputElement | null>(null)

/** 当前有效模型是否支持视觉输入 */
const visionEnabled = computed(() => {
  const modelId = sessionModel.value || settings.currentModel
  return settings.modelSupportsVision(modelId)
})

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

/**
 * 长边 > MAX_IMAGE_LONG_EDGE 时按比例缩放到 MAX_IMAGE_LONG_EDGE，否则原样返回。
 * GIF 跳过缩放以保留动画；PNG 保留原格式以保留透明，其余统一输出 JPEG (q=0.92)。
 * 缩放失败时静默返回原 dataUrl。
 */
async function resizeImageIfNeeded(file: File, dataUrl: string): Promise<string> {
  if (file.type === 'image/gif') return dataUrl
  try {
    const img = await loadImage(dataUrl)
    const longEdge = Math.max(img.naturalWidth, img.naturalHeight)
    if (longEdge <= MAX_IMAGE_LONG_EDGE) return dataUrl

    const scale = MAX_IMAGE_LONG_EDGE / longEdge
    const w = Math.round(img.naturalWidth * scale)
    const h = Math.round(img.naturalHeight * scale)
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) return dataUrl
    ctx.drawImage(img, 0, 0, w, h)
    const outputType = file.type === 'image/png' ? 'image/png' : 'image/jpeg'
    return canvas.toDataURL(outputType, outputType === 'image/jpeg' ? 0.92 : undefined)
  } catch (e) {
    console.warn('图片缩放失败，使用原图:', e)
    return dataUrl
  }
}

async function addImageFiles(files: FileList | File[]) {
  for (const file of Array.from(files)) {
    if (!file.type.startsWith('image/')) continue
    if (file.size > MAX_IMAGE_SIZE) {
      message.warning(`图片 ${file.name} 超过 10MB 限制`)
      continue
    }
    const dataUrl = await readFileAsDataURL(file)
    const finalUrl = await resizeImageIfNeeded(file, dataUrl)
    attachedImages.value.push(finalUrl)
  }
}

function removeImage(index: number) {
  attachedImages.value.splice(index, 1)
}

function onClickUpload() {
  fileInputRef.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) addImageFiles(input.files)
  input.value = ''  // 重置，允许重复选择同一文件
}

function onClickUploadFile() {
  fileInputRef2.value?.click()
}

function onFileInputChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) addFiles(input.files)
  input.value = ''
}

function getFileExtension(filename: string): string {
  const parts = filename.split('.')
  if (parts.length > 1) {
    const ext = parts[parts.length - 1]
    return ext ? ext.toLowerCase() : ''
  }
  return ''
}


async function addFiles(files: FileList | File[]) {
  for (const file of Array.from(files)) {
    if (file.size > MAX_FILE_SIZE) {
      message.warning(`文件 ${file.name} 超过 10MB 限制`)
      continue
    }
    const ext = getFileExtension(file.name)
    if (!SUPPORTED_FILE_EXTENSIONS.has(ext)) {
      message.warning(`不支持的文件类型: .${ext}`)
      continue
    }
    try {
      const content = await readFileAsDataURL(file)
      attachedFiles.value.push({
        name: file.name,
        size: file.size,
        content
      })
    } catch (e) {
      message.error(`读取文件 ${file.name} 失败`)
    }
  }
}

function removeFile(index: number) {
  attachedFiles.value.splice(index, 1)
}

const allMessages = computed(() => {
  const msgs = [...chat.messages]
  if (chat.streamingMessage) msgs.push(chat.streamingMessage)
  return msgs
})

// ── 智能滚动：用户向上翻时不强制滚到底部 ─────────────────────────────────────
//
// 实现要点：
// 1. 通过 messagesEndRef 哨兵元素用 .closest() 可靠地找到 NScrollbar 的滚动容器
//    （避免直接访问 NScrollbar 暴露的 containerRef，它是 Vue Ref 对象而非 HTMLElement）
// 2. 用 programmaticScroll 标志位区分代码触发的滚动和用户手动滚动
// 3. 直接操作 scrollContainer.scrollTop（不用 behavior:'smooth'），
//    避免平滑动画期间多次触发 scroll 事件把标志位意外重置

const isUserScrolledUp = ref(false)
const messagesEndRef = ref<HTMLElement | null>(null)  // 消息列表底部哨兵
let scrollContainer: HTMLElement | null = null
let programmaticScroll = false

function handleScroll() {
  // 跳过代码触发的滚动事件
  if (programmaticScroll) {
    programmaticScroll = false
    return
  }
  if (!scrollContainer) return
  const dist = scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight
  isUserScrolledUp.value = dist > 150
}

onMounted(() => {
  nextTick(() => {
    // 优先通过 scrollbarRef.$el 找滚动容器，fallback 到哨兵元素向上遍历
    const rootEl = scrollbarRef.value?.$el as HTMLElement | undefined
    scrollContainer = rootEl?.querySelector('.n-scrollbar-container') as HTMLElement | null
      ?? messagesEndRef.value?.closest('.n-scrollbar-container') as HTMLElement | null
    scrollContainer?.addEventListener('scroll', handleScroll, { passive: true })
  })
})

onUnmounted(() => {
  scrollContainer?.removeEventListener('scroll', handleScroll)
})

function scrollToBottom(force = false) {
  if (!force && isUserScrolledUp.value) return
  nextTick(() => {
    if (!scrollContainer) return
    programmaticScroll = true
    scrollContainer.scrollTop = scrollContainer.scrollHeight  // 即时滚动，不触发动画
  })
}

// 每次消息更新时，若用户没有向上翻则自动跟踪到底部
watch(allMessages, () => scrollToBottom(), { deep: true })

async function sendMessage() {
  const content = inputText.value.trim()
  if ((!content && !attachedImages.value.length && !attachedFiles.value.length) || chat.isStreaming) return
  const images = attachedImages.value.length ? [...attachedImages.value] : undefined
  const files = attachedFiles.value.length ? attachedFiles.value.map(f => ({
    name: f.name,
    mime_type: getMimeType(f.name),
    content: f.content.split(',')[1] || f.content,  // 提取 base64 部分
    size: f.size,
  })) : undefined
  inputText.value = ''
  attachedImages.value = []
  attachedFiles.value = []
  isUserScrolledUp.value = false   // 用户主动发消息，强制回到底部
  scrollToBottom(true)
  await chat.sendMessage(content, images, files)
}

function getMimeType(filename: string): string {
  const ext = getFileExtension(filename)
  const mimeMap: Record<string, string> = {
    'txt': 'text/plain',
    'md': 'text/markdown',
    'json': 'application/json',
    'csv': 'text/csv',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  }
  return mimeMap[ext] || 'text/plain'
}

function handleKeydown(e: KeyboardEvent) {
  // 如果 @mention 面板正在处理，让它先消费键盘
  if (handleMentionKeydown(e)) return
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    sendMessage()
  }
}

// ── 拖拽和粘贴图片 ───────────────────────────────────────────────────────────
function handleDrop(e: DragEvent) {
  e.preventDefault()
  const files = e.dataTransfer?.files
  if (!files?.length) return

  // 分离图片和其他文件
  const imageFiles: File[] = []
  const otherFiles: File[] = []

  for (const file of Array.from(files)) {
    if (file.type.startsWith('image/')) {
      imageFiles.push(file)
    } else {
      otherFiles.push(file)
    }
  }

  // 添加图片（如果启用视觉输入）
  if (imageFiles.length && visionEnabled.value) {
    addImageFiles(imageFiles)
  }

  // 添加其他文件
  if (otherFiles.length) {
    addFiles(otherFiles)
  }
}

function handlePaste(e: ClipboardEvent) {
  if (!visionEnabled.value) return
  const items = e.clipboardData?.items
  if (!items) return
  const imageFiles: File[] = []
  for (const item of Array.from(items)) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) imageFiles.push(file)
    }
  }
  if (imageFiles.length) {
    e.preventDefault()
    addImageFiles(imageFiles)
  }
}

// ── 提示词模板选择器 ─────────────────────────────────────────────────────────
const templates = ref<PromptTemplate[]>([])
const showTemplatePicker = ref(false)
const templateSearch = ref('')

async function loadTemplates() {
  try {
    const data = await api.templates.list()
    templates.value = data.templates
  } catch (e) { console.error(e) }
}

// 按分类分组
const groupedTemplates = computed(() => {
  const filtered = templates.value.filter(t =>
    !templateSearch.value || t.name.includes(templateSearch.value) || t.category.includes(templateSearch.value)
  )
  const groups: Record<string, PromptTemplate[]> = {}
  for (const t of filtered) {
    if (!groups[t.category]) groups[t.category] = []
    ;(groups[t.category] as PromptTemplate[]).push(t)
  }
  return groups
})

function applyTemplate(tpl: PromptTemplate) {
  inputText.value = tpl.content
  showTemplatePicker.value = false
  // 聚焦输入框
  nextTick(() => {
    const el = document.querySelector('.message-input textarea') as HTMLTextAreaElement | null
    el?.focus()
  })
}

// ── 会话工具开关 ─────────────────────────────────────────────────────────────
const toolStates = ref<ToolState[]>([])
const sessionOverrides = ref<Record<string, boolean>>({})
const showToolPanel = ref(false)
const savingTool = ref<string | null>(null)

async function loadToolStates() {
  if (!chat.currentSessionId) return
  try {
    const data = await api.toolState.getAll(chat.currentSessionId)
    toolStates.value = data.tools
    sessionOverrides.value = data.session_overrides
  } catch (e) { console.error(e) }
}

async function toggleGlobalTool(toolName: string) {
  savingTool.value = toolName
  try {
    const res = await api.toolState.toggleGlobal(toolName)
    const t = toolStates.value.find(x => x.name === toolName)
    if (t) {
      t.global_enabled = res.globally_enabled
      // 重新计算 effective
      const override = sessionOverrides.value[toolName]
      t.effective_enabled = override !== undefined ? override : res.globally_enabled
      t.scope = override !== undefined ? (override ? 'session_on' : 'session_off') : 'global'
    }
    message.success(`工具「${toolName}」全局${res.globally_enabled ? '已启用' : '已禁用'}`)
  } catch (e) { message.error(String(e)) } finally { savingTool.value = null }
}

async function setSessionOverride(toolName: string, value: boolean | null) {
  if (!chat.currentSessionId) return
  savingTool.value = toolName
  try {
    const res = await api.toolState.setSessionOverrides(chat.currentSessionId, { [toolName]: value })
    sessionOverrides.value = res.tool_overrides
    // 刷新该工具状态
    await loadToolStates()
  } catch (e) { message.error(String(e)) } finally { savingTool.value = null }
}

// 打开工具面板时加载，会话切换时也刷新
watch(() => chat.currentSessionId, (id) => {
  if (id) { loadToolStates(); syncSessionModel() }
}, { immediate: true })

watch(showToolPanel, (v) => { if (v) loadToolStates() })

// ── 会话专属模型 ─────────────────────────────────────────────────────────────

/** 当前会话的专属模型，null = 跟随全局 */
const sessionModel = ref<string | null>(null)
const savingModel = ref(false)

/** 从 chat store 的 currentSession 同步会话模型 */
function syncSessionModel() {
  sessionModel.value = chat.currentSession?.model ?? null
}
watch(() => chat.currentSession, syncSessionModel)

/** 有效模型：会话专属 > 全局 */
const effectiveModel = computed(() =>
  sessionModel.value || settings.currentModel
)

/** 当前会话的上下文用量：取最后一条 assistant 消息的 inputTokens vs 模型上下文窗口 */
const contextUsage = computed(() => {
  const msgs = chat.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    const m = msgs[i]
    if (m && m.role === 'assistant' && m.inputTokens != null) {
      const params = settings.getModelParams(effectiveModel.value)
      const pct = Math.round((m.inputTokens / params.context_window_tokens) * 100)
      return { used: m.inputTokens, total: params.context_window_tokens, pct }
    }
  }
  return null
})

async function setSessionModel(modelId: string | null | undefined) {
  if (!chat.currentSessionId) return
  // 空字符串 / undefined 视为清除
  const value = modelId || null
  savingModel.value = true
  try {
    await api.sessions.setModel(chat.currentSessionId, value)
    sessionModel.value = value
    // 同步 session 对象（无需整体刷新列表）
    if (chat.currentSession) {
      chat.currentSession.model = value
    }
    if (value) {
      message.success(`此会话将使用模型: ${value}`)
    } else {
      message.info(`已恢复跟随全局模型: ${settings.currentModel}`)
    }
  } catch (e) {
    message.error('设置会话模型失败')
  } finally {
    savingModel.value = false
  }
}

// 检测当前会话是否为运行中的子任务（用于空消息列表时的状态提示）
const isViewingRunningSubAgent = computed(() => {
  const id = chat.currentSessionId
  if (!id) return false
  return chat.getRunningSubAgent(id) !== undefined
})

// ── 工具确认卡片 ─────────────────────────────────────────────────────────────
const pendingConfirms = computed(() => {
  const id = chat.currentSessionId
  if (!id) return []
  const state = chat.getSessionState(id)
  return Array.from(state.pendingConfirms.values())
})

function handleConfirmDecide(id: string, decision: ConfirmDecision, extra?: string) {
  const sid = chat.currentSessionId
  if (!sid) return
  chat.sendConfirmResponse(sid, id, decision, extra)
}

// ── 会话工作目录 ─────────────────────────────────────────────────────────────
const workingDir = computed(() => chat.currentSession?.working_dir || null)
const showWorkingDirPicker = ref(false)
const workingDirLabel = computed(() => {
  if (!workingDir.value) return '默认 workspace'
  const parts = workingDir.value.split('/').filter(Boolean)
  return parts[parts.length - 1] || workingDir.value
})

async function submitWorkingDir(dir: string | null) {
  const sid = chat.currentSessionId
  if (!sid) return
  try {
    const res = await api.sessions.setWorkingDir(sid, dir)
    if (chat.currentSession) chat.currentSession.working_dir = res.working_dir
    showWorkingDirPicker.value = false
    if (res.working_dir) message.success(`工作目录已设为 ${res.working_dir}`)
    else message.info('已回落到默认 workspace')
  } catch (e: any) {
    message.error(`设置工作目录失败: ${e?.message || e}`)
  }
}

// 加载模板
loadTemplates()

// 监听 chat.requestInsertToInput：追加路径到输入框末尾
watch(() => chat.pendingInsert, (v) => {
  if (!v) return
  const cur = inputText.value
  // 在光标位置或末尾插入；这里用最简策略：末尾追加，前后各补空格
  const needsLeadingSpace = cur.length > 0 && !cur.endsWith(' ') && !cur.endsWith('\n')
  inputText.value = cur + (needsLeadingSpace ? ' ' : '') + v.text + ' '
  nextTick(() => {
    const el = document.querySelector('.message-input textarea') as HTMLTextAreaElement | null
    el?.focus()
    if (el) {
      el.selectionStart = el.selectionEnd = el.value.length
    }
  })
})

// 供 App.vue 顶层监听 workingDir 变化
defineExpose({ workingDir })

/** chip 显示用：目录 + 文件名，太长时截断中间 */
function shortPath(p: string): string {
  if (p.length <= 42) return p
  const parts = p.split('/')
  const last = parts.pop() || p
  return `…/${last}`
}

// ── @mention 补全 ─────────────────────────────────────────────────────────
//
// 在 textarea 里检测最后一个未闭合的 @<query>，弹出 MentionPopover。
// - 只在光标位置的 token 边界起效（@ 前必须是行首或空白）
// - Enter/Tab 选中；Esc 关闭
// - 选中后：调用 chat.addAttachment，把输入框里的 `@query` 片段删掉
//
const mentionShow = ref(false)
const mentionQuery = ref('')
const mentionCandidates = ref<MentionCandidate[]>([])
const mentionActiveIdx = ref(0)
const mentionLoading = ref(false)
const mentionAnchorLeft = ref(0)
const mentionAnchorBottom = ref(0)
let mentionRange: { start: number; end: number } | null = null
let mentionDebounce: number | null = null

/** 从光标向前找最近的 @：位于行首或空白之后才算 mention 触发点 */
function detectMention(el: HTMLTextAreaElement): { query: string; start: number; end: number } | null {
  const value = el.value
  const caret = el.selectionStart ?? value.length
  if (caret === 0) return null
  // 从光标向前扫描到最近的 @ 或空白
  let i = caret - 1
  while (i >= 0) {
    const ch = value[i]
    if (ch === '@') {
      // 检查 @ 前一位必须是行首或空白
      const prev = i > 0 ? value[i - 1] : ''
      if (i === 0 || prev === ' ' || prev === '\n' || prev === '\t') {
        const q = value.slice(i + 1, caret)
        // query 不能含空白 / 换行
        if (/\s/.test(q)) return null
        return { query: q, start: i, end: caret }
      }
      return null
    }
    if (ch === ' ' || ch === '\n' || ch === '\t') return null
    i--
  }
  return null
}

async function requestMention(q: string) {
  const sid = chat.currentSessionId
  if (!sid) return
  mentionLoading.value = true
  try {
    const data = await api.sessions.searchFiles(sid, q, 30)
    mentionCandidates.value = data.results
    mentionActiveIdx.value = 0
  } catch {
    mentionCandidates.value = []
  } finally {
    mentionLoading.value = false
  }
}

function scheduleMentionFetch(q: string) {
  if (mentionDebounce != null) window.clearTimeout(mentionDebounce)
  mentionDebounce = window.setTimeout(() => {
    requestMention(q)
    mentionDebounce = null
  }, 120)
}

function positionMentionPopover(el: HTMLTextAreaElement) {
  // 简单方案：popover 挂在 textarea 上方，left 对齐 textarea 左边
  const chatPanel = el.closest('.chat-panel') as HTMLElement | null
  if (!chatPanel) return
  const panelRect = chatPanel.getBoundingClientRect()
  const taRect = el.getBoundingClientRect()
  mentionAnchorLeft.value = taRect.left - panelRect.left
  // bottom 计算：距离 panel 底部的距离
  mentionAnchorBottom.value = panelRect.bottom - taRect.top + 4
}

function onInputChange() {
  const el = document.querySelector('.message-input textarea') as HTMLTextAreaElement | null
  if (!el || !chat.currentSession?.working_dir) {
    mentionShow.value = false
    return
  }
  const det = detectMention(el)
  if (!det) {
    mentionShow.value = false
    mentionRange = null
    return
  }
  mentionRange = { start: det.start, end: det.end }
  mentionQuery.value = det.query
  mentionShow.value = true
  positionMentionPopover(el)
  scheduleMentionFetch(det.query)
}

function acceptMention(c: MentionCandidate) {
  if (!mentionRange) { mentionShow.value = false; return }
  const added = chat.addAttachment(c.path)
  if (!added) message.info(`${c.path} 已在附加列表中`)
  // 把输入框里的 @xxx 段删掉
  const before = inputText.value.slice(0, mentionRange.start)
  const after = inputText.value.slice(mentionRange.end)
  inputText.value = before + after
  mentionShow.value = false
  mentionRange = null
  nextTick(() => {
    const el = document.querySelector('.message-input textarea') as HTMLTextAreaElement | null
    if (el) {
      el.focus()
      el.selectionStart = el.selectionEnd = before.length
    }
  })
}

/** 键盘事件在 mention 打开时优先处理 */
function handleMentionKeydown(e: KeyboardEvent): boolean {
  if (!mentionShow.value) return false
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    mentionActiveIdx.value = Math.min(mentionActiveIdx.value + 1, mentionCandidates.value.length - 1)
    return true
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    mentionActiveIdx.value = Math.max(mentionActiveIdx.value - 1, 0)
    return true
  }
  if (e.key === 'Enter' || e.key === 'Tab') {
    const c = mentionCandidates.value[mentionActiveIdx.value]
    if (c) {
      e.preventDefault()
      acceptMention(c)
      return true
    }
  }
  if (e.key === 'Escape') {
    e.preventDefault()
    mentionShow.value = false
    return true
  }
  return false
}
</script>

<template>
  <div class="chat-panel" :class="{ 'has-working-dir': !!workingDir }">
    <!-- 顶部标题栏 -->
    <div class="chat-header">
      <span class="chat-title" :title="chat.currentSession?.title">
        {{ chat.currentSession?.title || '选择或创建会话' }}
      </span>
      <div class="header-actions">
        <NTooltip v-if="chat.currentSession">
          <template #trigger>
            <button
              class="chip"
              :class="{ active: !!workingDir }"
              @click="showWorkingDirPicker = true"
            >
              <span class="chip-emoji">🗂</span>
              <span class="chip-text">{{ workingDirLabel }}</span>
            </button>
          </template>
          {{ workingDir ? `会话工作目录：${workingDir}` : '点击设置会话工作目录（AI 编码模式）' }}
        </NTooltip>
        <NTooltip v-if="contextUsage" placement="bottom">
          <template #trigger>
            <span class="chip context-usage" :class="{ warn: contextUsage.pct >= 60, danger: contextUsage.pct >= 80 }">
              <span class="chip-emoji">📊</span>
              <span class="chip-text">{{ contextUsage.pct }}%</span>
            </span>
          </template>
          已使用 {{ contextUsage.used.toLocaleString() }} / {{ contextUsage.total.toLocaleString() }} tokens
        </NTooltip>
        <span class="header-divider" />
        <NTooltip>
          <template #trigger>
            <button class="icon-btn" :class="{ active: !!workingDir }" @click="toggleTerminal" :disabled="!workingDir">🖥</button>
          </template>
          {{ workingDir ? '本地终端（在 cwd 中打开）' : '需要先设置会话工作目录' }}
        </NTooltip>
        <NTooltip>
          <template #trigger>
            <button class="icon-btn" @click="openScheduler">⏰</button>
          </template>
          定时任务
        </NTooltip>
        <NTooltip>
          <template #trigger>
            <button class="icon-btn" @click="openSettings">⚙️</button>
          </template>
          系统设置
        </NTooltip>
      </div>
    </div>

    <!-- 消息区域 -->
    <NScrollbar ref="scrollbarRef" class="messages-area">
      <div class="messages-container">
        <div v-if="allMessages.length === 0 && isViewingRunningSubAgent" class="subagent-running-hint">
          <NSpin size="medium" />
          <span>子任务执行中，完成后自动刷新…</span>
        </div>
        <NEmpty
          v-else-if="allMessages.length === 0 && !chat.isStreaming"
          description="发送消息开始对话"
          class="empty-chat"
        />
        <template v-for="msg in allMessages" :key="msg.id">
          <MessageBubble :message="msg" />
          <!-- SubAgent 块：渲染在对应的 assistant 消息下方 -->
          <template v-if="msg.role === 'assistant' && msg.subAgents?.length">
            <SubAgentBlock
              v-for="sa in msg.subAgents"
              :key="sa.id"
              :subAgent="sa"
            />
          </template>
        </template>
        <div v-if="chat.isStreaming && !chat.streamingMessage" class="typing-indicator">
          <NSpin size="small" />
          <span>思考中…</span>
        </div>

        <!-- 破坏性工具确认卡片（会话内联渲染） -->
        <ToolConfirmDialog
          v-for="cf in pendingConfirms"
          :key="cf.id"
          :confirm="cf"
          @decide="(d, extra) => handleConfirmDecide(cf.id, d, extra)"
        />

        <!-- 底部哨兵：用于定位 NScrollbar 的滚动容器，不可见 -->
        <div ref="messagesEndRef" />
      </div>
    </NScrollbar>

    <!-- 输入区域 -->
    <div class="input-area" v-if="chat.currentSessionId">
      <!-- 工具栏：会话模型 + 模板选择 + 工具开关 -->
      <div class="input-toolbar">

        <!-- 会话专属模型选择器 -->
        <NPopover
          trigger="click"
          placement="top-start"
          :style="{ width: '300px' }"
        >
          <template #trigger>
            <NTooltip>
              <template #trigger>
                <NButton
                  size="small"
                  quaternary
                  :type="sessionModel ? 'warning' : 'default'"
                >
                  🤖 {{ sessionModel ? sessionModel.split('/').pop() : '会话模型' }}
                </NButton>
              </template>
              {{ sessionModel ? `当前会话使用: ${sessionModel}` : '为此会话单独选择模型（不影响全局）' }}
            </NTooltip>
          </template>

          <div class="model-popover">
            <div class="model-popover-title">
              会话专属模型
              <span class="model-popover-hint">不影响全局 · 实际: {{ effectiveModel.split('/').pop() }}</span>
            </div>
            <NSelect
              :value="sessionModel || ''"
              :options="[
                { value: '', label: `🌐 跟随全局 (${settings.currentModel.split('/').pop()})` },
                ...settings.modelSelectOptions
              ]"
              filterable
              placeholder="搜索或选择模型…"
              size="small"
              :loading="savingModel"
              style="width: 100%"
              @update:value="setSessionModel"
            />
          </div>
        </NPopover>

        <!-- 模板选择器 -->
        <NPopover
          v-model:show="showTemplatePicker"
          trigger="click"
          placement="top-start"
          :style="{ width: '340px', maxHeight: '420px' }"
          scrollable
        >
          <template #trigger>
            <NTooltip>
              <template #trigger>
                <NButton size="small" quaternary @click="showTemplatePicker = !showTemplatePicker">
                  📋 模板
                </NButton>
              </template>
              选择提示词模板
            </NTooltip>
          </template>

          <div class="template-picker">
            <NInput
              v-model:value="templateSearch"
              size="small"
              placeholder="搜索模板…"
              clearable
              style="margin-bottom: 8px"
            />
            <template v-if="Object.keys(groupedTemplates).length === 0">
              <div class="empty-tip">暂无模板，可在设置中添加</div>
            </template>
            <template v-for="(items, category) in groupedTemplates" :key="category">
              <div class="tpl-category">{{ category }}</div>
              <div
                v-for="tpl in items"
                :key="tpl.id"
                class="tpl-item"
                @click="applyTemplate(tpl)"
              >
                <span class="tpl-name">{{ tpl.name }}</span>
                <span class="tpl-preview">{{ tpl.content.slice(0, 40) }}…</span>
              </div>
            </template>
          </div>
        </NPopover>

        <!-- 工具开关面板 -->
        <NPopover
          v-model:show="showToolPanel"
          trigger="click"
          placement="top-start"
          :style="{ width: '440px', maxHeight: '500px' }"
          scrollable
        >
          <template #trigger>
            <NTooltip>
              <template #trigger>
                <NButton size="small" quaternary @click="showToolPanel = !showToolPanel">
                  🔧 工具
                </NButton>
              </template>
              管理本会话可用工具
            </NTooltip>
          </template>

          <div class="tool-panel">
            <div class="tool-panel-header">
              <span>工具热插拔</span>
              <NTag size="small" type="info">会话级优先于全局</NTag>
            </div>
            <div class="tool-panel-legend">
              <NTag size="tiny" type="success">会话启用</NTag>
              <NTag size="tiny" type="error">会话禁用</NTag>
              <NTag size="tiny">跟随全局</NTag>
            </div>
            <NDivider style="margin: 8px 0" />

            <div v-for="tool in toolStates" :key="tool.name" class="tool-row">
              <div class="tool-info">
                <span class="tool-name" :title="tool.name">{{ tool.name }}</span>
                <NTag
                  size="tiny"
                  :type="tool.effective_enabled ? 'success' : 'error'"
                  style="flex-shrink: 0"
                >{{ tool.effective_enabled ? '启用' : '禁用' }}</NTag>
                <NTag
                  v-if="tool.scope !== 'global'"
                  size="tiny"
                  :type="tool.scope === 'session_on' ? 'success' : 'error'"
                  style="flex-shrink: 0"
                >会话覆盖</NTag>
              </div>
              <div class="tool-controls">
                <!-- 会话级覆盖 -->
                <NTooltip>
                  <template #trigger>
                    <NButton
                      size="tiny"
                      :type="tool.scope === 'session_on' ? 'success' : 'default'"
                      :ghost="tool.scope !== 'session_on'"
                      :loading="savingTool === tool.name"
                      @click="setSessionOverride(tool.name, tool.scope === 'session_on' ? null : true)"
                    >启</NButton>
                  </template>
                  {{ tool.scope === 'session_on' ? '点击取消会话启用' : '为本会话强制启用' }}
                </NTooltip>
                <NTooltip>
                  <template #trigger>
                    <NButton
                      size="tiny"
                      :type="tool.scope === 'session_off' ? 'error' : 'default'"
                      :ghost="tool.scope !== 'session_off'"
                      :loading="savingTool === tool.name"
                      @click="setSessionOverride(tool.name, tool.scope === 'session_off' ? null : false)"
                    >禁</NButton>
                  </template>
                  {{ tool.scope === 'session_off' ? '点击取消会话禁用' : '为本会话强制禁用' }}
                </NTooltip>
                <!-- 全局开关 -->
                <NTooltip>
                  <template #trigger>
                    <NSwitch
                      :value="tool.global_enabled"
                      size="small"
                      :loading="savingTool === tool.name"
                      @update:value="toggleGlobalTool(tool.name)"
                    />
                  </template>
                  全局{{ tool.global_enabled ? '已启用' : '已禁用' }}（影响所有会话）
                </NTooltip>
              </div>
            </div>
          </div>
        </NPopover>
      </div>

      <!-- 输入框 + 发送按钮 -->
      <div class="input-row" @drop.prevent="handleDrop" @dragover.prevent @paste="handlePaste">
        <!-- @ 引用附件 chip 条（发一次消费一次） -->
        <div v-if="chat.pendingAttachments.length" class="pending-attachments">
          <div class="pa-label">📎 附加到本条：</div>
          <div class="pa-chips">
            <span
              v-for="p in chat.pendingAttachments"
              :key="p"
              class="pa-chip"
              :title="p"
            >
              <span class="pa-chip-name">{{ shortPath(p) }}</span>
              <button class="pa-chip-x" @click="chat.removeAttachment(p)" title="移除">✕</button>
            </span>
            <button class="pa-clear" @click="chat.clearAttachments()">清空</button>
          </div>
        </div>
        <!-- 图片预览区 -->
        <div v-if="attachedImages.length" class="attached-images">
          <div v-for="(img, idx) in attachedImages" :key="idx" class="attached-image-item">
            <img :src="img" class="attached-thumb" />
            <button class="remove-image-btn" @click="removeImage(idx)">✕</button>
          </div>
        </div>
        <!-- 文件附件区 -->
        <div v-if="attachedFiles.length" class="attached-files">
          <div v-for="(file, idx) in attachedFiles" :key="idx" class="attached-file-item">
            <span class="file-name">📎 {{ file.name }}</span>
            <button class="remove-file-btn" @click="removeFile(idx)">✕</button>
          </div>
        </div>
        <div class="input-main">
          <NInput
            v-model:value="inputText"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 16 }"
            :placeholder="chat.isStreaming ? '等待响应完成…' : '发送消息（Enter 发送，Shift+Enter 换行；输入 @ 可引用文件）'"
            :disabled="chat.isStreaming"
            @keydown="handleKeydown"
            @input="onInputChange"
            @focus="onInputChange"
            @click="onInputChange"
            class="message-input"
          />
          <div class="input-actions">
            <!-- 图片上传按钮 -->
            <NTooltip v-if="visionEnabled">
              <template #trigger>
                <NButton size="medium" quaternary @click="onClickUpload" :disabled="chat.isStreaming">
                  🖼️
                </NButton>
              </template>
              上传图片（支持拖拽或 Ctrl+V 粘贴）
            </NTooltip>
            <input ref="fileInputRef" type="file" accept="image/*" multiple hidden @change="onFileChange" />
            <!-- 文件上传按钮 -->
            <NTooltip>
              <template #trigger>
                <NButton size="medium" quaternary @click="onClickUploadFile" :disabled="chat.isStreaming">
                  📁
                </NButton>
              </template>
              上传文件（支持拖拽）
            </NTooltip>
            <input ref="fileInputRef2" type="file" multiple hidden @change="onFileInputChange" />
            <!-- 发送/停止按钮 -->
            <NTooltip v-if="chat.isStreaming">
              <template #trigger>
                <NButton type="error" size="large" @click="chat.stopStreaming()">停止</NButton>
              </template>
              停止当前响应
            </NTooltip>
            <NButton
              v-else
              type="primary"
              size="large"
              :disabled="!inputText.trim() && !attachedImages.length && !attachedFiles.length"
              @click="sendMessage"
            >发送</NButton>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="no-session-hint">
      请从左侧选择或创建一个会话
    </div>

    <!-- 工作目录选择器 -->
    <WorkingDirPicker
      v-model:show="showWorkingDirPicker"
      :current-dir="workingDir"
      @submit="submitWorkingDir"
    />

    <!-- @mention 补全下拉 -->
    <MentionPopover
      v-if="mentionShow"
      :candidates="mentionCandidates"
      :active-index="mentionActiveIdx"
      :loading="mentionLoading"
      :query="mentionQuery"
      :anchor-left="mentionAnchorLeft"
      :anchor-bottom="mentionAnchorBottom"
      @pick="acceptMention"
      @hover-index="(i) => (mentionActiveIdx = i)"
    />
  </div>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: white;
  position: relative;  /* 供 MentionPopover 绝对定位使用 */
}

.chat-header {
  padding: 10px 16px;
  border-bottom: 1px solid #ececec;
  background: white;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 52px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: auto;
}

.header-divider {
  width: 1px;
  height: 16px;
  background: #e5e7eb;
  margin: 0 4px;
}

.chat-title {
  font-weight: 600;
  font-size: 15px;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1 1 auto;
  min-width: 0;
}

/* 通用 chip 样式（工作目录、上下文百分比等） */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #6b7280;
  border-radius: 999px;
  padding: 3px 10px 3px 8px;
  font-size: 12px;
  line-height: 18px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
  max-width: 220px;
}
.chip:hover {
  border-color: #cbd5e1;
  background: white;
  color: #374151;
}
.chip.active {
  color: #1677ff;
  background: #eef4ff;
  border-color: #bfd4ff;
}
.chip-emoji { font-size: 11px; line-height: 1; }
.chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.context-usage {
  color: #16a34a;
  background: #f0fdf4;
  border-color: #bbf7d0;
  cursor: default;
}
.context-usage:hover { background: #f0fdf4; color: #16a34a; border-color: #bbf7d0; }

.context-usage.warn {
  color: #b45309;
  background: #fffbeb;
  border-color: #fde68a;
}
.context-usage.warn:hover { background: #fffbeb; color: #b45309; border-color: #fde68a; }

.context-usage.danger {
  color: #b91c1c;
  background: #fef2f2;
  border-color: #fecaca;
}
.context-usage.danger:hover { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }

/* icon 按钮（⏰ ⚙️） */
.icon-btn {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.icon-btn:hover { background: #f3f4f6; }

.messages-area { flex: 1; }
.messages-container { padding: 16px 20px; min-height: 100%; }
.empty-chat { margin-top: 60px; }

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  color: #888;
  font-size: 13px;
}

.subagent-running-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 80px;
  color: #888;
  font-size: 13px;
}

.input-area {
  border-top: 1px solid #e8e8e8;
  padding: 10px 20px 16px;
}

.input-toolbar {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  align-items: center;
}

/* 会话模型 popover */
.model-popover {
  padding: 4px 2px;
}

.model-popover-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-popover-hint {
  font-size: 11px;
  font-weight: 400;
  color: #999;
}

.input-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attached-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* @ 附件 chip 条 */
.pending-attachments {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 10px;
  background: #f0f7ff;
  border: 1px dashed #bfd4ff;
  border-radius: 8px;
  font-size: 12px;
  color: #1e40af;
}

.pa-label {
  flex-shrink: 0;
  font-weight: 500;
  color: #2563eb;
  padding-top: 3px;
}

.pa-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.pa-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: white;
  border: 1px solid #bfd4ff;
  border-radius: 6px;
  padding: 2px 4px 2px 8px;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 11px;
  color: #1e40af;
  max-width: 260px;
}

.pa-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.pa-chip-x {
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  padding: 0 3px;
  font-size: 11px;
  border-radius: 3px;
  flex-shrink: 0;
}
.pa-chip-x:hover { background: #fee2e2; color: #dc2626; }

.pa-clear {
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  align-self: center;
}
.pa-clear:hover { background: rgba(37, 99, 235, 0.08); color: #2563eb; }

.attached-image-item {
  position: relative;
  display: inline-block;
}

.attached-files {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 6px;
  border: 1px dashed #d9d9d9;
}

.attached-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: #595959;
  padding: 4px 0;
}

.file-name {
  word-break: break-all;
  flex: 1;
}

.remove-file-btn {
  background: transparent;
  border: none;
  color: #999;
  cursor: pointer;
  padding: 2px 4px;
  font-size: 16px;
}

.remove-file-btn:hover {
  color: #ff4d4f;
}

.attached-thumb {
  width: 96px;
  height: 96px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #d9d9d9;
}

.remove-image-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: #ff4d4f;
  color: white;
  font-size: 12px;
  line-height: 22px;
  text-align: center;
  cursor: pointer;
  padding: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.input-main {
  display: flex;
  gap: 10px;
  align-items: stretch;
}

.input-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
  justify-content: flex-end;
}

.message-input { flex: 1; }

/* 让 NInput textarea 支持手动拖拽调整高度 */
.message-input :deep(textarea) {
  resize: vertical;
  min-height: 100px;
  font-size: 14px;
  line-height: 1.6;
}

/* 发送/停止按钮加大 */
.input-actions :deep(.n-button) {
  min-width: 72px;
}

.no-session-hint {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #aaa;
  font-size: 14px;
}

/* 模板选择器 */
.template-picker { font-size: 13px; }

.tpl-category {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 8px 0 4px;
  padding: 0 2px;
}

.tpl-item {
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
  transition: background 0.15s;
}
.tpl-item:hover { background: #f3f4f6; }

.tpl-name { font-weight: 500; color: #1a1a1a; }
.tpl-preview { font-size: 11px; color: #999; }
.empty-tip { color: #aaa; text-align: center; padding: 12px 0; font-size: 13px; }

/* 工具面板 */
.tool-panel { font-size: 13px; }

.tool-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  margin-bottom: 4px;
}

.tool-panel-legend {
  display: flex;
  gap: 6px;
  font-size: 11px;
  margin-bottom: 2px;
}

.tool-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid #f3f4f6;
}
.tool-row:last-child { border-bottom: none; }

.tool-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-size: 12px;
  font-family: monospace;
  color: #333;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
</style>
