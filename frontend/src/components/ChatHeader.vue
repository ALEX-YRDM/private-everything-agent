<script setup lang="ts">
/**
 * 聊天页顶部工具栏：会话标题 / cwd chip / token 用量 chip / 终端-主题-日程-设置 图标。
 *
 * 保持无状态：状态从 props 传入；行为通过 emit 或 inject 提供的 App 级动作触发。
 */
import { inject, watch, onMounted } from 'vue'
import { NTooltip, useMessage } from 'naive-ui'
import { useChatStore } from '../stores/chat'
import { useThemeStore } from '../stores/theme'

interface ContextUsage {
  used: number
  total: number
  pct: number
}

defineProps<{
  workingDir: string | null
  workingDirLabel: string
  contextUsage: ContextUsage | null
  themeIcon: string
  themeTip: string
}>()

const emit = defineEmits<{
  'open-working-dir-picker': []
}>()

const chat = useChatStore()
const theme = useThemeStore()
const msg = useMessage()

// 会话切换时刷新 plan-mode 状态；组件挂载时立刻拉一次
watch(() => chat.currentSessionId, (sid) => {
  if (sid) chat.refreshPlanMode(sid)
})
onMounted(() => {
  if (chat.currentSessionId) chat.refreshPlanMode(chat.currentSessionId)
})

async function togglePlanMode() {
  try {
    await chat.setPlanMode(!chat.planMode)
    msg.success(chat.planMode ? '已进入 Plan Mode：只出方案不执行' : '已退出 Plan Mode')
  } catch (e: any) {
    msg.error(`切换失败：${e?.message || e}`)
  }
}

// App.vue provide 的三个动作（在 ChatPanel 里已经 inject 过，这里再 inject 一次是纯 lookup）
const openScheduler = inject<() => void>('openScheduler', () => {})
const openSettings = inject<() => void>('openSettings', () => {})
const toggleTerminal = inject<() => void>('toggleTerminal', () => {})
</script>

<template>
  <div class="chat-header">
    <span class="chat-title" :title="chat.currentSession?.title">
      {{ chat.currentSession?.title || '选择或创建会话' }}
    </span>
    <div class="header-actions">
      <NTooltip v-if="chat.currentSession">
        <template #trigger>
          <button
            class="chip"
            :class="{ active: chat.planMode, warn: chat.planMode }"
            @click="togglePlanMode"
          >
            <span class="chip-emoji">🧭</span>
            <span class="chip-text">Plan{{ chat.planMode ? ' · 开' : '' }}</span>
          </button>
        </template>
        {{ chat.planMode
          ? 'Plan Mode：只出方案不执行破坏性工具。点击退出。'
          : '进入 Plan Mode：Agent 只出方案不执行，适合大改动前对齐'
        }}
      </NTooltip>
      <NTooltip v-if="chat.currentSession">
        <template #trigger>
          <button
            class="chip"
            :class="{ active: !!workingDir }"
            @click="emit('open-working-dir-picker')"
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
          <button class="icon-btn" @click="toggleTerminal" title="打开/关闭终端">🖥</button>
        </template>
        {{ workingDir ? '本地终端（在 cwd 中打开）' : '本地终端（默认 workspace）' }}
      </NTooltip>
      <NTooltip>
        <template #trigger>
          <button class="icon-btn" @click="theme.cycle()">{{ themeIcon }}</button>
        </template>
        {{ themeTip }}
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
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid var(--md-border);
  background: var(--md-bg);
  gap: 12px;
  flex-shrink: 0;
  min-height: 44px;
}

.chat-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--md-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* chip 通用 */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--md-border);
  border-radius: 999px;
  background: var(--md-bg-subtle);
  color: var(--md-text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.chip:hover {
  background: var(--md-bg-muted);
  color: var(--md-text-primary);
}
.chip.active {
  border-color: var(--md-brand);
  background: var(--md-brand-soft);
  color: var(--md-brand-strong);
}
.chip.warn {
  border-color: var(--md-warning);
  background: var(--md-warning-soft);
  color: var(--md-warning);
}
.chip-emoji {
  font-size: 12px;
}
.chip-text {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-usage {
  cursor: default;
}
.context-usage.warn {
  background: var(--md-warning-soft);
  color: var(--md-warning);
  border-color: var(--md-warning);
}
.context-usage.danger {
  background: var(--md-danger-soft);
  color: var(--md-danger);
  border-color: var(--md-danger);
}

.header-divider {
  width: 1px;
  height: 20px;
  background: var(--md-border);
  margin: 0 2px;
}

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
.icon-btn:hover {
  background: var(--md-bg-muted);
  color: var(--md-text-primary);
}
</style>
