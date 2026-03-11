<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { NButton, NInput, NPopconfirm, NTooltip, NScrollbar } from 'naive-ui'

const chat = useChatStore()
const editingId = ref<string | null>(null)
const editingTitle = ref('')

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

    <NScrollbar class="sessions-scroll">
      <div
        v-for="session in chat.sessions"
        :key="session.id"
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

      <div v-if="chat.sessions.length === 0" class="empty-state">
        <p>暂无会话</p>
        <NButton @click="chat.createSession()">创建第一个会话</NButton>
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
