<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  NDrawer, NDrawerContent, NButton, NModal, NForm, NFormItem,
  NInput, NSwitch, NSpace, NTag, NPopconfirm, useMessage, NEmpty,
  NTooltip,
} from 'naive-ui'
import { api, type ScheduledTask } from '../api/http'
import { useChatStore } from '../stores/chat'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [v: boolean] }>()

const message = useMessage()
const chat = useChatStore()

const tasks = ref<ScheduledTask[]>([])
const showModal = ref(false)
const editingTask = ref<ScheduledTask | null>(null)

const form = ref({
  name: '',
  cron_expr: '0 8 * * *',
  prompt: '',
  model_id: '',
})

// cron 预设
const cronPresets = [
  { label: '每天早上 8:00', value: '0 8 * * *' },
  { label: '每天中午 12:00', value: '0 12 * * *' },
  { label: '每天晚上 21:00', value: '0 21 * * *' },
  { label: '每周一早上 9:00', value: '0 9 * * 1' },
  { label: '每小时整点', value: '0 * * * *' },
  { label: '每30分钟', value: '*/30 * * * *' },
  { label: '每5分钟（间隔）', value: '@every 5m' },
  { label: '每30秒（间隔）', value: '@every 30s' },
  { label: '每2小时（间隔）', value: '@every 2h' },
]

// prompt 模板
const promptTemplates = [
  {
    label: '每日简报（新闻+股票）',
    value: `请帮我获取今日的信息摘要，包括：
1. 搜索今日国内重要新闻（3-5条）
2. 搜索今日国际重要新闻（2-3条）
3. 搜索A股主要指数（上证、深证、创业板）今日表现
4. 搜索美股主要指数（道琼斯、纳斯达克、标普500）昨日收盘
请用简洁清晰的格式整理输出。`,
  },
  {
    label: '每日科技资讯',
    value: `请搜索并汇总今日科技行业重要动态：
1. AI/大模型领域最新进展（2-3条）
2. 国内外科技公司重要新闻（2-3条）
3. 开源社区/GitHub 热门项目
请附上信息来源链接。`,
  },
  {
    label: '周报整理提醒',
    value: `今天是周五，请帮我整理本周工作情况：
1. 用 list_dir 查看工作目录最近修改的文件
2. 提醒我本周应该完成的工作
请输出周报草稿框架，方便我填写。`,
  },
]

async function loadTasks() {
  try {
    const data = await api.tasks.list()
    tasks.value = data.tasks
  } catch (e) {
    console.error(e)
  }
}

function openCreate() {
  editingTask.value = null
  form.value = { name: '', cron_expr: '0 8 * * *', prompt: '', model_id: '' }
  showModal.value = true
}

function openEdit(task: ScheduledTask) {
  editingTask.value = task
  form.value = {
    name: task.name,
    cron_expr: task.cron_expr,
    prompt: task.prompt,
    model_id: task.model_id || '',
  }
  showModal.value = true
}

async function saveTask() {
  if (!form.value.name.trim() || !form.value.cron_expr.trim() || !form.value.prompt.trim()) {
    message.warning('请填写任务名称、cron 表达式和执行 Prompt')
    return
  }
  try {
    const payload = {
      ...form.value,
      model_id: form.value.model_id || undefined,
    }
    if (editingTask.value) {
      await api.tasks.update(editingTask.value.id, payload)
      message.success('任务已更新')
    } else {
      await api.tasks.create(payload)
      message.success('任务已创建')
    }
    showModal.value = false
    await loadTasks()
  } catch (e: unknown) {
    message.error(String(e))
  }
}

async function toggleTask(task: ScheduledTask) {
  try {
    await api.tasks.update(task.id, { enabled: task.enabled ? 0 : 1 } as never)
    await loadTasks()
    message.success(task.enabled ? '任务已暂停' : '任务已启用')
  } catch (e: unknown) {
    message.error(String(e))
  }
}

async function deleteTask(id: number) {
  try {
    await api.tasks.delete(id)
    message.success('已删除')
    await loadTasks()
  } catch (e: unknown) {
    message.error(String(e))
  }
}

async function runNow(task: ScheduledTask) {
  try {
    await api.tasks.runNow(task.id)
    message.success('任务已触发，结果将保存到对应会话')
    // 刷新会话列表
    setTimeout(() => chat.loadSessions(), 2000)
  } catch (e: unknown) {
    message.error(String(e))
  }
}

async function goToSession(sessionId: string) {
  emit('update:show', false)
  await chat.switchSession(sessionId)
}

function applyPreset(preset: { value: string }) {
  form.value.cron_expr = preset.value
}

function applyTemplate(tpl: { value: string }) {
  form.value.prompt = tpl.value
}

function formatLastRun(task: ScheduledTask) {
  if (!task.last_run_at) return '从未运行'
  return new Date(task.last_run_at).toLocaleString('zh-CN')
}

function statusType(task: ScheduledTask): 'success' | 'error' | 'default' {
  if (!task.last_status) return 'default'
  if (task.last_status === 'success') return 'success'
  if (task.last_status.startsWith('error')) return 'error'
  return 'default'
}

// 面板打开时加载任务
watch(() => props.show, (v) => { if (v) loadTasks() }, { immediate: true })

// Agent 执行任务工具（create/delete/update）后自动刷新
watch(() => chat.tasksChangedAt, () => { loadTasks() })
</script>

<template>
  <NDrawer :show="show" @update:show="emit('update:show', $event)" :width="540" placement="right">
    <NDrawerContent :native-scrollbar="false">
      <template #header>
        <div class="drawer-header">
          <span>⏰ 定时任务</span>
          <NButton size="small" type="primary" @click="openCreate">+ 新建任务</NButton>
        </div>
      </template>

      <NEmpty v-if="tasks.length === 0" description="暂无定时任务" style="margin-top: 40px">
        <template #extra>
          <NButton @click="openCreate">创建第一个任务</NButton>
        </template>
      </NEmpty>

      <div v-else class="task-list">
        <div v-for="task in tasks" :key="task.id" class="task-card">
          <div class="task-top">
            <div class="task-info">
              <span class="task-name">{{ task.name }}</span>
              <code class="cron-badge">{{ task.cron_expr }}</code>
              <NTag v-if="task.last_status" :type="statusType(task)" size="tiny">
                {{ task.last_status === 'success' ? '成功' : task.last_status }}
              </NTag>
            </div>
            <NSwitch
              :value="!!task.enabled"
              size="small"
              @update:value="toggleTask(task)"
            />
          </div>

          <p class="task-prompt">{{ task.prompt.slice(0, 80) }}{{ task.prompt.length > 80 ? '…' : '' }}</p>

          <div class="task-footer">
            <span class="last-run">上次: {{ formatLastRun(task) }}</span>
            <NSpace>
              <NTooltip v-if="task.session_id">
                <template #trigger>
                  <NButton size="tiny" @click="goToSession(task.session_id!)">查看结果</NButton>
                </template>
                跳转到任务会话
              </NTooltip>
              <NButton size="tiny" @click="runNow(task)">立即执行</NButton>
              <NButton size="tiny" @click="openEdit(task)">编辑</NButton>
              <NPopconfirm @positive-click="deleteTask(task.id)">
                <template #trigger>
                  <NButton size="tiny" type="error">删除</NButton>
                </template>
                确定删除任务「{{ task.name }}」？
              </NPopconfirm>
            </NSpace>
          </div>
        </div>
      </div>
    </NDrawerContent>
  </NDrawer>

  <!-- 新建/编辑任务 Modal -->
  <NModal v-model:show="showModal" :title="editingTask ? '编辑任务' : '新建定时任务'"
          preset="card" style="width: 500px; max-height: 90vh; overflow-y: auto">
    <NForm label-placement="top">
      <NFormItem label="任务名称" required>
        <NInput v-model:value="form.name" placeholder="如：每日简报" />
      </NFormItem>

      <NFormItem required>
        <template #label>
          <span>Cron 表达式</span>
          <span class="field-hint">（分 时 日 月 周）</span>
        </template>
        <NInput v-model:value="form.cron_expr" placeholder="0 8 * * *" style="margin-bottom: 8px" />
        <NSpace wrap>
          <NButton v-for="p in cronPresets" :key="p.value" size="tiny"
                   @click="applyPreset(p)">{{ p.label }}</NButton>
        </NSpace>
      </NFormItem>

      <NFormItem required>
        <template #label>
          <span>执行 Prompt</span>
          <span class="field-hint">（Agent 将用此 prompt 执行任务）</span>
        </template>
        <NInput v-model:value="form.prompt" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }"
                placeholder="输入 Agent 执行的指令..." style="margin-bottom: 8px" />
        <div class="template-label">快速填充模板：</div>
        <NSpace wrap>
          <NButton v-for="t in promptTemplates" :key="t.label" size="tiny"
                   @click="applyTemplate(t)">{{ t.label }}</NButton>
        </NSpace>
      </NFormItem>

      <NFormItem label="指定模型（可选）">
        <NInput v-model:value="form.model_id" placeholder="留空则使用系统默认模型" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showModal = false">取消</NButton>
        <NButton type="primary" @click="saveTask">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  padding: 12px 14px;
  background: #fafafa;
}

.task-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.task-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.task-name {
  font-weight: 600;
  font-size: 14px;
}

.cron-badge {
  background: #e6f0ff;
  color: #1677ff;
  padding: 1px 7px;
  border-radius: 6px;
  font-size: 12px;
  font-family: monospace;
}

.task-prompt {
  font-size: 12px;
  color: #777;
  margin: 4px 0 8px;
  line-height: 1.5;
}

.task-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.last-run {
  font-size: 11px;
  color: #aaa;
}

.field-hint {
  font-size: 11px;
  color: #aaa;
  margin-left: 6px;
  font-weight: normal;
}

.template-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}
</style>
