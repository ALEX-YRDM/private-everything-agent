<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import {
  NInput, NButton, NScrollbar, NSpin, NEmpty, NTooltip,
  NPopover, NDivider, NSwitch, NTag, NSelect,
  useMessage,
} from 'naive-ui'
import MessageBubble from './MessageBubble.vue'
import SubAgentBlock from './SubAgentBlock.vue'
import { useChatStore } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'
import { api, type PromptTemplate, type ToolState } from '../api/http'

const chat = useChatStore()
const settings = useSettingsStore()
const message = useMessage()
const inputText = ref('')
const scrollbarRef = ref<InstanceType<typeof NScrollbar> | null>(null)

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
    // 从哨兵元素向上遍历 DOM 找到 NScrollbar 的滚动容器（稳定可靠）
    scrollContainer = messagesEndRef.value?.closest('.n-scrollbar-container') as HTMLElement | null
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
  if (!content || chat.isStreaming) return
  inputText.value = ''
  isUserScrolledUp.value = false   // 用户主动发消息，强制回到底部
  scrollToBottom(true)
  await chat.sendMessage(content)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    sendMessage()
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

// 加载模板
loadTemplates()
</script>

<template>
  <div class="chat-panel">
    <!-- 顶部标题栏 -->
    <div class="chat-header">
      <span class="chat-title">
        {{ chat.currentSession?.title || '选择或创建会话' }}
      </span>
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
                  size="tiny"
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
                <NButton size="tiny" quaternary @click="showTemplatePicker = !showTemplatePicker">
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
                <NButton size="tiny" quaternary @click="showToolPanel = !showToolPanel">
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
      <div class="input-row">
        <NInput
          v-model:value="inputText"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 12 }"
          :placeholder="chat.isStreaming ? '等待响应完成…' : '发送消息（Enter 发送，Shift+Enter 换行）'"
          :disabled="chat.isStreaming"
          @keydown="handleKeydown"
          class="message-input"
        />
        <div class="send-btn">
          <NTooltip v-if="chat.isStreaming">
            <template #trigger>
              <NButton type="error" size="medium" @click="chat.stopStreaming()">停止</NButton>
            </template>
            停止当前响应
          </NTooltip>
          <NButton
            v-else
            type="primary"
            size="medium"
            :disabled="!inputText.trim()"
            @click="sendMessage"
          >发送</NButton>
        </div>
      </div>
    </div>

    <div v-else class="no-session-hint">
      请从左侧选择或创建一个会话
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: white;
}

.chat-header {
  padding: 14px 20px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  min-height: 52px;
}

.chat-title {
  font-weight: 600;
  font-size: 15px;
  color: #1a1a1a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

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
  padding: 8px 16px 12px;
}

.input-toolbar {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
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
  gap: 8px;
  align-items: flex-end;
}

.message-input { flex: 1; }

.send-btn { flex-shrink: 0; }

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
