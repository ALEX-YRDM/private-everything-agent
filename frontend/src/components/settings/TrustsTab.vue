<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { NEmpty, NButton, NInput, NPopconfirm, NTag, NTooltip, NSelect, useMessage } from 'naive-ui'
import { api } from '../../api/http'
import { useChatStore } from '../../stores/chat'

const chat = useChatStore()
const message = useMessage()

const loading = ref(false)
const paths = ref<string[]>([])
const commands = ref<string[]>([])
const targetSessionId = ref<string | null>(null)

const newPath = ref('')
const newCommand = ref('')

const sessionOptions = computed(() =>
  chat.sessions.map((s) => ({
    label: `${s.title}${s.working_dir ? ` · ${s.working_dir.split('/').pop()}` : ''}`,
    value: s.id,
  })),
)

async function load() {
  const sid = targetSessionId.value
  if (!sid) {
    paths.value = []
    commands.value = []
    return
  }
  loading.value = true
  try {
    const data = await api.sessions.getTrusts(sid)
    paths.value = data.paths
    commands.value = data.commands
  } catch (e: any) {
    message.error(`加载失败: ${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

async function addPath() {
  const v = newPath.value.trim()
  if (!v) return
  const sid = targetSessionId.value
  if (!sid) return
  try {
    const data = await api.sessions.addTrust(sid, 'path', v)
    paths.value = data.paths
    commands.value = data.commands
    newPath.value = ''
    message.success(`已信任目录 ${v}`)
  } catch (e: any) {
    message.error(String(e?.message || e))
  }
}

async function addCommand() {
  const v = newCommand.value.trim()
  if (!v) return
  const sid = targetSessionId.value
  if (!sid) return
  try {
    const data = await api.sessions.addTrust(sid, 'command', v)
    paths.value = data.paths
    commands.value = data.commands
    newCommand.value = ''
    message.success(`已信任命令前缀 "${v}"`)
  } catch (e: any) {
    message.error(String(e?.message || e))
  }
}

async function removeTrust(kind: 'path' | 'command', value: string) {
  const sid = targetSessionId.value
  if (!sid) return
  try {
    const data = await api.sessions.removeTrust(sid, kind, value)
    paths.value = data.paths
    commands.value = data.commands
    message.success('已移除')
  } catch (e: any) {
    message.error(String(e?.message || e))
  }
}

// 默认追当前会话
watch(
  () => chat.currentSessionId,
  (id) => {
    targetSessionId.value = id
    load()
  },
  { immediate: true },
)

watch(targetSessionId, load)
</script>

<template>
  <div class="trusts-tab">
    <div class="tt-desc">
      信任列表让 Agent 在执行 <code>exec</code> / 文件修改类工具时，
      对匹配的路径或命令前缀直接跳过确认弹窗。仅对当前会话生效。
    </div>

    <div class="tt-session-picker">
      <span class="tt-label">会话</span>
      <NSelect
        v-model:value="targetSessionId"
        :options="sessionOptions"
        placeholder="选择要管理的会话"
        size="small"
        filterable
      />
    </div>

    <div v-if="!targetSessionId" class="tt-empty">
      <NEmpty description="请先选择一个会话" size="small" />
    </div>

    <template v-else>
      <section class="tt-section">
        <div class="tt-section-head">
          <span class="tt-section-title">🛡 信任的目录（trust_path）</span>
          <NTag size="tiny" :type="paths.length ? 'info' : 'default'">{{ paths.length }}</NTag>
        </div>
        <div class="tt-add-row">
          <NInput
            v-model:value="newPath"
            size="small"
            placeholder="绝对路径，如 /Users/foo/code/my-project"
            @keydown.enter="addPath"
          />
          <NButton type="primary" size="small" @click="addPath" :disabled="!newPath.trim()">
            添加
          </NButton>
        </div>
        <div v-if="!paths.length" class="tt-list-empty">尚未信任任何目录</div>
        <div v-else class="tt-list">
          <div v-for="p in paths" :key="p" class="tt-row">
            <span class="tt-icon">📁</span>
            <code class="tt-value" :title="p">{{ p }}</code>
            <NPopconfirm @positive-click="removeTrust('path', p)">
              <template #trigger>
                <NTooltip>
                  <template #trigger>
                    <button class="tt-remove">✕</button>
                  </template>
                  移除
                </NTooltip>
              </template>
              确定要撤销对此目录的信任吗？
            </NPopconfirm>
          </div>
        </div>
      </section>

      <section class="tt-section">
        <div class="tt-section-head">
          <span class="tt-section-title">⚡ 信任的命令前缀（trust_command）</span>
          <NTag size="tiny" :type="commands.length ? 'info' : 'default'">{{ commands.length }}</NTag>
        </div>
        <div class="tt-add-row">
          <NInput
            v-model:value="newCommand"
            size="small"
            placeholder='命令前缀，如 "npm run " 或 "git status"'
            @keydown.enter="addCommand"
          />
          <NButton type="primary" size="small" @click="addCommand" :disabled="!newCommand.trim()">
            添加
          </NButton>
        </div>
        <div v-if="!commands.length" class="tt-list-empty">尚未信任任何命令前缀</div>
        <div v-else class="tt-list">
          <div v-for="c in commands" :key="c" class="tt-row">
            <span class="tt-icon">⚡</span>
            <code class="tt-value" :title="c">{{ c }}</code>
            <NPopconfirm @positive-click="removeTrust('command', c)">
              <template #trigger>
                <NTooltip>
                  <template #trigger>
                    <button class="tt-remove">✕</button>
                  </template>
                  移除
                </NTooltip>
              </template>
              确定要撤销对此命令的信任吗？
            </NPopconfirm>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.trusts-tab {
  padding: 12px 4px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tt-desc {
  font-size: 12.5px;
  color: #6b7280;
  line-height: 1.6;
  padding: 10px 12px;
  background: #f9fafb;
  border-radius: 6px;
  border-left: 3px solid #93c5fd;
}
.tt-desc code {
  font-family: 'SF Mono', 'Monaco', monospace;
  background: white;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11.5px;
  color: #1677ff;
}

.tt-session-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tt-label {
  font-size: 12px;
  color: #6b7280;
  flex-shrink: 0;
}

.tt-empty { padding: 30px 0; }

.tt-section {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 12px;
  background: white;
}

.tt-section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.tt-section-title {
  font-weight: 600;
  font-size: 13px;
  color: #1f2937;
}

.tt-add-row {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.tt-list-empty {
  font-size: 12px;
  color: #9ca3af;
  padding: 8px 4px;
  text-align: center;
}

.tt-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tt-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid transparent;
  transition: border-color 0.15s;
}
.tt-row:hover { border-color: #e5e7eb; }

.tt-icon { flex-shrink: 0; font-size: 12px; }

.tt-value {
  flex: 1;
  min-width: 0;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tt-remove {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.15s, color 0.15s;
}
.tt-remove:hover { background: #fee2e2; color: #dc2626; }
</style>
