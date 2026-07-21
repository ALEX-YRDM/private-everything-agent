<script setup lang="ts">
/**
 * Todo 面板：右上角悬浮卡片。
 * - Agent 通过 todo_write 工具修改 todos，后端广播 todos_update 事件驱动更新
 * - 用户也能点勾选切换状态、双击文本改内容、删除
 * - 折叠态下只显示"n / m 完成"胶囊
 */
import { computed, ref, watch } from 'vue'
import { NButton } from 'naive-ui'
import { useChatStore } from '../stores/chat'
import type { TodoItem } from '../api/websocket'

const chat = useChatStore()

const expanded = ref(false)
const editingId = ref<string | null>(null)
const editingText = ref('')

// 切会话时拉一次；没有 SSE 推送时也能同步
watch(() => chat.currentSessionId, (sid) => {
  if (sid) chat.refreshTodos(sid)
}, { immediate: true })

const todos = computed(() => chat.currentTodos)

const doneCount = computed(() => todos.value.filter(t => t.status === 'completed').length)
const runningCount = computed(() => todos.value.filter(t => t.status === 'in_progress').length)

const hasAny = computed(() => todos.value.length > 0)

async function persist(next: TodoItem[]) {
  const sid = chat.currentSessionId
  if (!sid) return
  try {
    await chat.saveTodos(sid, next)
  } catch (e) {
    console.error('保存 todos 失败', e)
  }
}

function cycleStatus(t: TodoItem) {
  const next: TodoItem['status'] =
    t.status === 'pending' ? 'in_progress'
    : t.status === 'in_progress' ? 'completed'
    : 'pending'
  const updated = todos.value.map(x => x.id === t.id ? { ...x, status: next } : x)
  persist(updated)
}

function removeTodo(id: string) {
  persist(todos.value.filter(t => t.id !== id))
}

function startEdit(t: TodoItem) {
  editingId.value = t.id
  editingText.value = t.content
}
function commitEdit(id: string) {
  const text = editingText.value.trim()
  if (text) {
    persist(todos.value.map(t => t.id === id ? { ...t, content: text } : t))
  }
  editingId.value = null
}
function cancelEdit() { editingId.value = null }

function statusIcon(s: TodoItem['status']): string {
  return s === 'completed' ? '✅' : s === 'in_progress' ? '🔄' : '⭕'
}
</script>

<template>
  <div v-if="chat.currentSessionId && hasAny" class="todo-panel" :class="{ collapsed: !expanded }">
    <div class="tp-header" @click="expanded = !expanded">
      <span class="tp-title">📋 待办</span>
      <span class="tp-summary">
        <span v-if="runningCount > 0" class="pill running">{{ runningCount }} 进行</span>
        <span class="pill done">{{ doneCount }} / {{ todos.length }}</span>
      </span>
      <span class="tp-toggle">{{ expanded ? '▾' : '▸' }}</span>
    </div>

    <div v-if="expanded" class="tp-body">
      <div v-if="!hasAny" class="tp-empty">
        Agent 还没维护 todo。你也可以告诉它"列出计划"，或让它开始一个多步任务时自动生成。
      </div>
      <ul v-else class="tp-list">
        <li
          v-for="t in todos"
          :key="t.id"
          class="tp-item"
          :class="[`status-${t.status}`]"
        >
          <button class="tp-check" @click="cycleStatus(t)" :title="`当前：${t.status}，点击切换`">
            {{ statusIcon(t.status) }}
          </button>
          <template v-if="editingId === t.id">
            <input
              class="tp-edit-input"
              v-model="editingText"
              @blur="commitEdit(t.id)"
              @keydown.enter.stop="commitEdit(t.id)"
              @keydown.esc.stop="cancelEdit"
              autofocus
            />
          </template>
          <template v-else>
            <span class="tp-content" @dblclick="startEdit(t)">{{ t.content }}</span>
          </template>
          <button class="tp-remove" @click="removeTodo(t.id)" title="删除">✕</button>
        </li>
      </ul>
      <div class="tp-footer" v-if="hasAny">
        <NButton size="tiny" quaternary @click="persist([])">清空</NButton>
        <span class="tp-hint">双击文本可修改</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.todo-panel {
  position: fixed;
  top: 62px;
  right: 24px;
  width: 300px;
  background: var(--md-bg);
  border: 1px solid var(--md-border);
  border-radius: 10px;
  box-shadow: var(--md-shadow-md);
  z-index: 20;
  font-size: 13px;
  overflow: hidden;
}

.todo-panel.collapsed {
  width: auto;
}

.tp-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  background: var(--md-bg-subtle);
  border-bottom: 1px solid var(--md-border-soft);
}
.tp-header:hover { background: var(--md-bg-muted); }
.todo-panel.collapsed .tp-header { border-bottom: none; }

.tp-title {
  font-weight: 600;
  color: var(--md-text-primary);
}
.tp-summary {
  display: inline-flex;
  gap: 4px;
  margin-left: auto;
}
.pill {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  font-weight: 500;
}
.pill.done {
  background: var(--md-bg-muted);
  color: var(--md-text-secondary);
}
.pill.running {
  background: var(--md-warning-soft);
  color: var(--md-warning);
}
.tp-toggle {
  font-size: 11px;
  color: var(--md-text-muted);
}

.tp-body {
  padding: 8px 4px 8px;
  max-height: 60vh;
  overflow-y: auto;
}

.tp-empty {
  padding: 12px 10px;
  font-size: 12px;
  color: var(--md-text-muted);
  line-height: 1.5;
}

.tp-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.tp-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  transition: background 0.15s;
}
.tp-item:hover { background: var(--md-bg-subtle); }

.tp-item.status-completed .tp-content {
  color: var(--md-text-muted);
  text-decoration: line-through;
}
.tp-item.status-in_progress .tp-content {
  color: var(--md-warning);
  font-weight: 500;
}

.tp-check {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0 2px;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
}
.tp-content {
  flex: 1;
  min-width: 0;
  word-break: break-word;
  line-height: 1.4;
  cursor: text;
}
.tp-remove {
  border: none;
  background: transparent;
  color: var(--md-text-muted);
  cursor: pointer;
  padding: 0 4px;
  font-size: 12px;
  border-radius: 3px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}
.tp-item:hover .tp-remove { opacity: 1; }
.tp-remove:hover { color: var(--md-danger); background: var(--md-danger-soft); }

.tp-edit-input {
  flex: 1;
  border: 1px solid var(--md-brand);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 13px;
  font-family: inherit;
  background: var(--md-bg);
  color: var(--md-text-primary);
  outline: none;
}

.tp-footer {
  display: flex;
  align-items: center;
  padding: 4px 8px 2px;
  gap: 8px;
  border-top: 1px solid var(--md-border-soft);
  margin-top: 6px;
}
.tp-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--md-text-muted);
}
</style>
