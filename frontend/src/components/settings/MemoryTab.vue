<script setup lang="ts">
/**
 * 记忆管理：
 * - 全局用户画像（global_memory.memory_md）：跨会话共享
 * - 当前会话摘要（sessions.summary）：AutoCompact 产物，可编辑
 */
import { ref, onMounted, watch } from 'vue'
import { NInput, NButton, NSpin, NAlert, useMessage } from 'naive-ui'
import { useChatStore } from '../../stores/chat'

const chat = useChatStore()
const msg = useMessage()

const globalMemory = ref('')
const globalLoading = ref(false)
const globalSaving = ref(false)

const sessionSummary = ref('')
const summaryLoading = ref(false)
const summarySaving = ref(false)

async function loadGlobal() {
  globalLoading.value = true
  try {
    const r = await fetch('/api/memory')
    if (!r.ok) throw new Error(await r.text())
    const data = await r.json()
    globalMemory.value = data.memory_md ?? ''
  } catch (e: any) {
    msg.error(`加载全局记忆失败：${e?.message || e}`)
  } finally {
    globalLoading.value = false
  }
}

async function saveGlobal() {
  globalSaving.value = true
  try {
    const r = await fetch('/api/memory', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_md: globalMemory.value }),
    })
    if (!r.ok) throw new Error(await r.text())
    msg.success('已保存全局记忆')
  } catch (e: any) {
    msg.error(`保存失败：${e?.message || e}`)
  } finally {
    globalSaving.value = false
  }
}

async function loadSummary(sid: string | null) {
  sessionSummary.value = ''
  if (!sid) return
  summaryLoading.value = true
  try {
    const r = await fetch(`/api/sessions/${sid}/summary`)
    if (!r.ok) throw new Error(await r.text())
    const data = await r.json()
    sessionSummary.value = data.summary ?? ''
  } catch (e: any) {
    msg.error(`加载会话摘要失败：${e?.message || e}`)
  } finally {
    summaryLoading.value = false
  }
}

async function saveSummary() {
  const sid = chat.currentSessionId
  if (!sid) return
  summarySaving.value = true
  try {
    const r = await fetch(`/api/sessions/${sid}/summary`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summary: sessionSummary.value }),
    })
    if (!r.ok) throw new Error(await r.text())
    msg.success('已保存会话摘要')
  } catch (e: any) {
    msg.error(`保存失败：${e?.message || e}`)
  } finally {
    summarySaving.value = false
  }
}

async function clearGlobal() {
  if (!confirm('确定清空全局用户画像？此操作不可撤销。')) return
  globalMemory.value = ''
  await saveGlobal()
}

async function clearSummary() {
  if (!confirm('确定清空当前会话摘要？')) return
  sessionSummary.value = ''
  await saveSummary()
}

onMounted(() => {
  loadGlobal()
  loadSummary(chat.currentSessionId)
})

// 切会话时刷新摘要
watch(() => chat.currentSessionId, (sid) => loadSummary(sid))
</script>

<template>
  <div class="memory-tab">
    <NAlert type="info" :show-icon="false" style="margin-bottom: 16px">
      <div class="hint-line">
        <b>全局用户画像</b>：跨会话共享的长期记忆（偏好、技术栈、工作习惯）。
        Agent 会在 AutoCompact 后异步更新，你也可以在这里手动编辑或清空。
      </div>
      <div class="hint-line">
        <b>会话摘要</b>：单个会话超出上下文窗口 80% 时自动压缩产生。
      </div>
    </NAlert>

    <section class="mem-section">
      <div class="mem-header">
        <h3>🧠 全局用户画像</h3>
        <div class="mem-actions">
          <NButton size="small" @click="loadGlobal" :loading="globalLoading">刷新</NButton>
          <NButton size="small" @click="clearGlobal" :disabled="!globalMemory.trim()">清空</NButton>
          <NButton size="small" type="primary" :loading="globalSaving" @click="saveGlobal">
            保存
          </NButton>
        </div>
      </div>
      <NSpin v-if="globalLoading" size="small" />
      <NInput
        v-else
        v-model:value="globalMemory"
        type="textarea"
        :autosize="{ minRows: 6, maxRows: 20 }"
        placeholder="（尚无用户画像；Agent 会在合适时机自动补充）"
      />
    </section>

    <section class="mem-section">
      <div class="mem-header">
        <h3>📝 当前会话摘要</h3>
        <div class="mem-actions">
          <NButton
            size="small"
            @click="loadSummary(chat.currentSessionId)"
            :loading="summaryLoading"
            :disabled="!chat.currentSessionId"
          >刷新</NButton>
          <NButton size="small" @click="clearSummary" :disabled="!sessionSummary.trim() || !chat.currentSessionId">
            清空
          </NButton>
          <NButton size="small" type="primary" :loading="summarySaving" @click="saveSummary" :disabled="!chat.currentSessionId">
            保存
          </NButton>
        </div>
      </div>
      <div v-if="!chat.currentSessionId" class="mem-empty">请先选择一个会话</div>
      <NSpin v-else-if="summaryLoading" size="small" />
      <NInput
        v-else
        v-model:value="sessionSummary"
        type="textarea"
        :autosize="{ minRows: 6, maxRows: 20 }"
        placeholder="（尚无会话摘要；上下文使用超 80% 后会自动生成）"
      />
    </section>
  </div>
</template>

<style scoped>
.memory-tab {
  padding: 4px 2px 20px;
}

.hint-line {
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--md-text-secondary);
}
.hint-line + .hint-line { margin-top: 4px; }
.hint-line b { color: var(--md-text-primary); }

.mem-section {
  margin-bottom: 24px;
}

.mem-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  gap: 12px;
}
.mem-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--md-text-primary);
}
.mem-actions {
  display: flex;
  gap: 6px;
}

.mem-empty {
  padding: 20px;
  text-align: center;
  color: var(--md-text-muted);
  font-size: 13px;
  border: 1px dashed var(--md-border);
  border-radius: 8px;
}
</style>
