<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NDataTable, NButton, NSpace, NPopconfirm, NModal, NForm, NFormItem,
  NInput, NSelect, useMessage,
} from 'naive-ui'
import { api, type PromptTemplate } from '../../api/http'

const message = useMessage()
const templates = ref<PromptTemplate[]>([])
const showTplModal = ref(false)
const editingTpl = ref<PromptTemplate | null>(null)
const tplForm = ref({ name: '', content: '', category: '通用', sort_order: 0 })

const CATEGORIES = ['通用', '编程', '研究', '写作', '翻译', '效率', '其他']

async function loadTemplates() {
  try { templates.value = (await api.templates.list()).templates } catch (e) { console.error(e) }
}

function openCreateTpl() {
  editingTpl.value = null
  tplForm.value = { name: '', content: '', category: '通用', sort_order: 0 }
  showTplModal.value = true
}

function openEditTpl(tpl: PromptTemplate) {
  editingTpl.value = tpl
  tplForm.value = { name: tpl.name, content: tpl.content, category: tpl.category, sort_order: tpl.sort_order }
  showTplModal.value = true
}

async function saveTpl() {
  if (!tplForm.value.name.trim() || !tplForm.value.content.trim()) {
    message.warning('请填写模板名称和内容'); return
  }
  try {
    if (editingTpl.value) {
      await api.templates.update(editingTpl.value.id, tplForm.value)
      message.success('模板已更新')
    } else {
      await api.templates.create(tplForm.value)
      message.success('模板已创建')
    }
    showTplModal.value = false
    await loadTemplates()
  } catch (e) { message.error(String(e)) }
}

async function deleteTpl(tpl: PromptTemplate) {
  try {
    await api.templates.delete(tpl.id)
    await loadTemplates()
    message.success('已删除')
  } catch (e) { message.error(String(e)) }
}

const tplColumns = [
  { title: '名称', key: 'name', width: 120 },
  { title: '分类', key: 'category', width: 70 },
  { title: '内容预览', key: 'content',
    render: (row: PromptTemplate) => h('span', { style: 'color:#888;font-size:12px' },
      row.content.slice(0, 30) + (row.content.length > 30 ? '…' : ''))
  },
  { title: '操作', key: 'actions', width: 110,
    render: (row: PromptTemplate) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { size: 'tiny', onClick: () => openEditTpl(row) }, { default: () => '编辑' }),
        h(NPopconfirm, { onPositiveClick: () => deleteTpl(row) }, {
          trigger: () => h(NButton, { size: 'tiny', type: 'error', ghost: true }, { default: () => '删除' }),
          default: () => '确定删除此模板？',
        }),
      ],
    }),
  },
]

onMounted(loadTemplates)
</script>

<template>
  <div class="section">
    <div class="section-header">
      <h4>提示词模板（{{ templates.length }}）</h4>
      <NButton size="small" type="primary" @click="openCreateTpl">+ 新建</NButton>
    </div>
    <p class="hint">在聊天输入框点击「📋 模板」可快速选用。</p>
    <NDataTable :columns="tplColumns" :data="templates" size="small" :bordered="false" striped :max-height="400" />
  </div>

  <NModal v-model:show="showTplModal" preset="card" :title="editingTpl ? '编辑模板' : '新建提示词模板'" :style="{ width: '520px' }">
    <NForm label-placement="left" label-width="80">
      <NFormItem label="名称">
        <NInput v-model:value="tplForm.name" placeholder="如：代码审查" />
      </NFormItem>
      <NFormItem label="分类">
        <NSelect v-model:value="tplForm.category" :options="CATEGORIES.map(c => ({ value: c, label: c }))" tag placeholder="选择或输入分类" />
      </NFormItem>
      <NFormItem label="模板内容">
        <NInput v-model:value="tplForm.content" type="textarea" :autosize="{ minRows: 6, maxRows: 16 }" placeholder="输入提示词模板，用 [占位符] 标记需要填写的部分" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showTplModal = false">取消</NButton>
        <NButton type="primary" @click="saveTpl">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
@import './settings-common.css';
</style>