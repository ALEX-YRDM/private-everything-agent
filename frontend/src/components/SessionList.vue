<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '../stores/chat'
import { NButton, NInput, NPopconfirm, NTooltip, NScrollbar } from 'naive-ui'

const chat = useChatStore()
const editingId = ref<string | null>(null)
const editingTitle = ref('')
const searchQuery = ref('')
// 记录哪些 session 已展开子任务列表
const expandedSubSessions = ref<Set<string>>(new Set())

function startRename(id: string, currentTitle: string) {
  editingId.value = id
  editingTitle.value = currentTitle
}

async function confirmRename(id: string) {
  if (editingTitle.value.trim()) {
    await chat.renameSession(id, editingTitle.value.trim())
  }
  editingId.value = null
}

function cancelRename() {
  editingId.value = null
}

// 按 updated_at 降序排列（API 已排序，这里做前端二次保障），再按搜索词过滤
const filteredSessions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const sorted = [...chat.sessions].sort((a, b) => {
    return new Date(b.updated_at ?? b.created_at).getTime() -
           new Date(a.updated_at ?? a.created_at).getTime()
  })
  if (!q) return sorted
  return sorted.filter((s) => s.title.toLowerCase().includes(q))
})

async function toggleSubSessions(sessionId: string) {
  if (expandedSubSessions.value.has(sessionId)) {
    expandedSubSessions.value.delete(sessionId)
  } else {
    expandedSubSessions.value.add(sessionId)
    await chat.loadSubagentSessions(sessionId)
  }
}
</script>

<template>
  <div class="session-list">
    <div class="session-header">
      <span class="header-title">会话</span>
      <NTooltip>
        <template #trigger>
          <NButton size="small" circle @click="chat.createSession()">
            <template #icon>+</template>
          </NButton>
        </template>
        新建会话
      </NTooltip>
    </div>

    <div class="search-wrapper">
      <NInput
        v-model:value="searchQuery"
        size="small"
        placeholder="搜索会话..."
        clearable
      />
    </div>

    <NScrollbar class="sessions-scroll">
      <template v-for="session in filteredSessions" :key="session.id">
        <!-- 主 Session 行 -->
        <div
          class="session-item"
          :class="{ active: chat.currentSessionId === session.id }"
          @click="chat.switchSession(session.id)"
        >
          <template v-if="editingId === session.id">
            <NInput
              v-model:value="editingTitle"
              size="small"
              @blur="confirmRename(session.id)"
              @keydown.enter="confirmRename(session.id)"
              @keydown.esc="cancelRename"
              @click.stop
              autofocus
            />
          </template>
          <template v-else>
            <span class="session-title" @dblclick.stop="startRename(session.id, session.title)">
              {{ session.title }}
            </span>
            <div class="session-actions" @click.stop>
              <!-- 子任务展开按钮 -->
              <NTooltip>
                <template #trigger>
                  <button
                    class="action-btn sub-btn"
                    :class="{ active: expandedSubSessions.has(session.id) }"
                    @click="toggleSubSessions(session.id)"
                  >⚙</button>
                </template>
                {{ expandedSubSessions.has(session.id) ? '收起子任务会话' : '展开子任务会话' }}
              </NTooltip>
              <NTooltip>
                <template #trigger>
                  <button class="action-btn" @click="startRename(session.id, session.title)">✏️</button>
                </template>
                重命名
              </NTooltip>
              <NPopconfirm @positive-click="chat.deleteSession(session.id)">
                <template #trigger>
                  <button class="action-btn delete-btn">🗑️</button>
                </template>
                确定删除这个会话吗？
              </NPopconfirm>
            </div>
          </template>
        </div>

        <!-- 子 Session 列表（方案 B：折叠展示在主 Session 下方） -->
        <template v-if="expandedSubSessions.has(session.id)">
          <div
            v-for="sub in chat.getSubagentSessions(session.id)"
            :key="sub.id"
            class="session-item sub-session-item"
            :class="{ active: chat.currentSessionId === sub.id }"
            @click="chat.switchSession(sub.id)"
          >
            <span class="sub-session-indent">└</span>
            <span class="sub-session-icon">⚙</span>
            <span class="session-title sub-session-title">{{ sub.title }}</span>
          </div>
          <div
            v-if="chat.getSubagentSessions(session.id).length === 0"
            class="sub-session-empty"
          >
            暂无子任务会话
          </div>
        </template>
      </template>

      <div v-if="filteredSessions.length === 0" class="empty-state">
        <template v-if="searchQuery">
          <p>没有找到匹配的会话</p>
        </template>
        <template v-else>
          <p>暂无会话</p>
          <NButton @click="chat.createSession()">创建第一个会话</NButton>
        </template>
      </div>
    </NScrollbar>
  </div>
</template>

<style scoped>
.session-list {
  width: 240px;
  min-width: 200px;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 14px 12px;
  border-bottom: 1px solid #e8e8e8;
}

.header-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.search-wrapper {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
}

.sessions-scroll {
  flex: 1;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  border-radius: 8px;
  margin: 2px 6px;
  position: relative;
  min-height: 40px;
}

.session-item:hover {
  background: #efefef;
}

.session-item.active {
  background: #e6f0ff;
  color: #1677ff;
}

/* 子 Session 样式 */
.sub-session-item {
  padding: 6px 8px 6px 10px;
  min-height: 32px;
  margin: 1px 6px;
  border-radius: 6px;
  background: transparent;
}

.sub-session-item:hover {
  background: #f3f4f6;
}

.sub-session-item.active {
  background: #e6f0ff;
  color: #1677ff;
}

.sub-session-indent {
  color: #ccc;
  font-size: 12px;
  flex-shrink: 0;
  margin-right: 4px;
}

.sub-session-icon {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
  margin-right: 4px;
}

.sub-session-title {
  font-size: 12px;
  color: #666;
}

.sub-session-empty {
  padding: 4px 14px 4px 28px;
  font-size: 11px;
  color: #bbb;
}

.session-title {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-actions {
  display: none;
  gap: 4px;
}

.session-item:hover .session-actions,
.session-item.active .session-actions {
  display: flex;
}

.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 12px;
  opacity: 0.7;
}

.action-btn:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.08);
}

.delete-btn:hover {
  background: #fee;
}

/* 子任务展开按钮 */
.sub-btn {
  color: #666;
  font-size: 11px;
}

.sub-btn.active {
  color: #1677ff;
  background: #e6f0ff;
  opacity: 1;
}

.empty-state {
  padding: 24px 14px;
  text-align: center;
  color: #999;
  font-size: 13px;
}

.empty-state p {
  margin-bottom: 12px;
}
</style>
