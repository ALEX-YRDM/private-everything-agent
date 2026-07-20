<script setup lang="ts">
import { ref, watch } from 'vue'
import { NModal, NInput, NButton, NSpace, NTag, useMessage } from 'naive-ui'

const props = defineProps<{
  show: boolean
  currentDir?: string | null
}>()
const emit = defineEmits<{
  'update:show': [v: boolean]
  'submit': [dir: string | null]
}>()

const message = useMessage()
const RECENT_KEY = 'recent-working-dirs'
const RECENT_LIMIT = 8

const input = ref('')
const recent = ref<string[]>([])
const saving = ref(false)

function loadRecent() {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) recent.value = parsed.filter((x): x is string => typeof x === 'string')
    }
  } catch {
    recent.value = []
  }
}

function addToRecent(dir: string) {
  const next = [dir, ...recent.value.filter((d) => d !== dir)].slice(0, RECENT_LIMIT)
  recent.value = next
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {}
}

watch(() => props.show, (v) => {
  if (v) {
    input.value = props.currentDir || ''
    loadRecent()
  }
})

function pickRecent(dir: string) {
  input.value = dir
}

async function apply() {
  saving.value = true
  const value = input.value.trim()
  if (value && !value.startsWith('/') && !value.startsWith('~')) {
    message.warning('请填写绝对路径（以 / 或 ~ 开头）')
    saving.value = false
    return
  }
  const dir = value || null
  if (dir) addToRecent(dir)
  emit('submit', dir)
  saving.value = false
}

function clear() {
  emit('submit', null)
}
</script>

<template>
  <NModal
    :show="show"
    @update:show="emit('update:show', $event)"
    preset="card"
    title="设置会话工作目录"
    :style="{ width: '520px' }"
  >
    <div class="picker-body">
      <p class="hint">
        指定此会话的工作目录，Agent 的文件工具与 shell 命令都会以此为 cwd。
        留空可回落到全局 workspace（默认行为）。
      </p>
      <NInput
        v-model:value="input"
        placeholder="/Users/xxx/code/my-project"
        clearable
        @keydown.enter="apply"
      />

      <div v-if="recent.length" class="section">
        <div class="section-label">最近使用</div>
        <NSpace vertical size="small">
          <NTag
            v-for="dir in recent"
            :key="dir"
            :bordered="false"
            class="recent-tag"
            @click="pickRecent(dir)"
          >
            {{ dir }}
          </NTag>
        </NSpace>
      </div>
    </div>

    <template #footer>
      <NSpace justify="space-between">
        <NButton size="small" @click="clear">回落到 workspace</NButton>
        <NSpace>
          <NButton @click="emit('update:show', false)">取消</NButton>
          <NButton type="primary" :loading="saving" @click="apply">应用</NButton>
        </NSpace>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.picker-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hint {
  color: #888;
  font-size: 12px;
  margin: 0;
  line-height: 1.6;
}
.section {
  margin-top: 4px;
}
.section-label {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}
.recent-tag {
  cursor: pointer;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  transition: background 0.15s;
}
.recent-tag:hover {
  background: #e6f0ff;
  color: #1677ff;
}
</style>
