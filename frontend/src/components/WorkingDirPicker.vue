<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { NModal, NInput, NButton, NSpace, useMessage } from 'naive-ui'

const props = defineProps<{
  show: boolean
  currentDir?: string | null
}>()
const emit = defineEmits<{
  'update:show': [v: boolean]
  submit: [dir: string | null]
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

watch(
  () => props.show,
  (v) => {
    if (v) {
      input.value = props.currentDir || ''
      loadRecent()
    }
  },
)

function pickRecent(dir: string) {
  input.value = dir
}

const isValid = computed(() => {
  const v = input.value.trim()
  return !v || v.startsWith('/') || v.startsWith('~')
})

async function apply() {
  const value = input.value.trim()
  if (value && !isValid.value) {
    message.warning('请填写绝对路径（以 / 或 ~ 开头）')
    return
  }
  saving.value = true
  const dir = value || null
  if (dir) addToRecent(dir)
  emit('submit', dir)
  saving.value = false
}

function reset() {
  emit('submit', null)
}
</script>

<template>
  <NModal
    :show="show"
    @update:show="emit('update:show', $event)"
    preset="card"
    title="设置会话工作目录"
    :style="{ width: '560px' }"
  >
    <div class="wdp-body">
      <p class="wdp-hint">
        选定的目录会作为此会话所有文件工具与 shell 命令的 <code>cwd</code>，
        并激活右侧的项目文件树。留空回落到全局 workspace。
      </p>

      <div class="wdp-input-wrap">
        <NInput
          v-model:value="input"
          size="medium"
          placeholder="/Users/xxx/code/my-project"
          clearable
          :status="isValid ? undefined : 'error'"
          @keydown.enter="apply"
        >
          <template #prefix>
            <span class="wdp-input-prefix">🗂</span>
          </template>
        </NInput>
        <div v-if="!isValid" class="wdp-error">路径需以 / 或 ~ 开头</div>
      </div>

      <div v-if="recent.length" class="wdp-section">
        <div class="wdp-section-label">最近使用</div>
        <div class="wdp-recent-list">
          <button
            v-for="dir in recent"
            :key="dir"
            class="wdp-recent-item"
            :class="{ active: dir === input }"
            @click="pickRecent(dir)"
          >
            <span class="wdp-recent-icon">📁</span>
            <span class="wdp-recent-path">{{ dir }}</span>
          </button>
        </div>
      </div>
    </div>

    <template #footer>
      <NSpace justify="space-between">
        <NButton size="small" quaternary @click="reset">回落到 workspace</NButton>
        <NSpace>
          <NButton @click="emit('update:show', false)">取消</NButton>
          <NButton type="primary" :loading="saving" :disabled="!isValid" @click="apply">
            应用
          </NButton>
        </NSpace>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.wdp-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wdp-hint {
  color: #6b7280;
  font-size: 12.5px;
  margin: 0;
  line-height: 1.6;
}
.wdp-hint code {
  font-family: 'SF Mono', 'Monaco', monospace;
  background: #f3f4f6;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
}

.wdp-input-prefix {
  font-size: 14px;
  margin-right: 2px;
}
.wdp-error {
  font-size: 11.5px;
  color: #dc2626;
  margin-top: 4px;
  padding-left: 2px;
}

.wdp-section-label {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.wdp-recent-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.wdp-recent-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid transparent;
  background: #f9fafb;
  border-radius: 6px;
  cursor: pointer;
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  color: #374151;
  text-align: left;
  transition: background 0.15s, border-color 0.15s;
}
.wdp-recent-item:hover {
  background: white;
  border-color: #cbd5e1;
}
.wdp-recent-item.active {
  background: #eef4ff;
  border-color: #bfd4ff;
  color: #1e40af;
}

.wdp-recent-icon { flex-shrink: 0; }
.wdp-recent-path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
