<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NScrollbar, NEmpty, NSpin, NButton, NTooltip, useMessage } from 'naive-ui'
import FileTreeNode from './FileTreeNode.vue'
import { api, type FileNode } from '../api/http'

const props = defineProps<{
  sessionId: string | null
  workingDir: string | null
}>()
const emit = defineEmits<{
  'insert-path': [path: string]
}>()

const message = useMessage()
const root = ref<string>('')
const nodes = ref<FileNode[]>([])
/**
 * 已展开路径 map（path → true）。
 * 用普通对象而非 Set：Vue 3 响应式追踪属性访问，Set.has() 是方法调用
 * 不参与依赖收集，跨 props 传递后子组件无法在 Set 被替换时重渲。
 */
const expanded = ref<Record<string, boolean>>({})
/** path → children[] 的独立缓存 */
const childrenByPath = ref<Record<string, FileNode[]>>({})
const loading = ref(false)
/** 正在加载子节点的路径 map */
const loadingPaths = ref<Record<string, boolean>>({})

async function loadRoot() {
  if (!props.sessionId || !props.workingDir) {
    nodes.value = []
    return
  }
  loading.value = true
  try {
    const data = await api.sessions.listFiles(props.sessionId, '', 1)
    root.value = data.root
    nodes.value = data.entries
    childrenByPath.value = {}
    expanded.value = {}
    loadingPaths.value = {}
  } catch (e: any) {
    message.error(`加载文件树失败: ${e?.message || e}`)
    nodes.value = []
  } finally {
    loading.value = false
  }
}

async function onNodeClick(node: FileNode) {
  if (node.type === 'file') {
    emit('insert-path', node.path)
    return
  }
  // 目录：切换展开状态
  if (expanded.value[node.path]) {
    expanded.value = { ...expanded.value, [node.path]: false }
    return
  }
  expanded.value = { ...expanded.value, [node.path]: true }

  // 首次展开：拉取子节点
  if (!childrenByPath.value[node.path] && props.sessionId) {
    loadingPaths.value = { ...loadingPaths.value, [node.path]: true }
    try {
      const data = await api.sessions.listFiles(props.sessionId, node.path, 1)
      childrenByPath.value = { ...childrenByPath.value, [node.path]: data.entries }
    } catch (e: any) {
      message.warning(`加载 ${node.path} 失败: ${e?.message || e}`)
    } finally {
      const next = { ...loadingPaths.value }
      delete next[node.path]
      loadingPaths.value = next
    }
  }
}

watch(
  () => [props.sessionId, props.workingDir],
  () => loadRoot(),
  { immediate: true },
)

const displayRoot = computed(() => {
  if (!root.value) return ''
  const parts = root.value.split('/')
  return parts[parts.length - 1] || root.value
})
</script>

<template>
  <div class="file-tree-panel">
    <div class="file-tree-header">
      <span class="header-label">📁 {{ displayRoot || '文件树' }}</span>
      <NTooltip>
        <template #trigger>
          <NButton size="tiny" quaternary @click="loadRoot" :loading="loading">刷新</NButton>
        </template>
        重新读取当前目录
      </NTooltip>
    </div>
    <div v-if="root" class="root-path" :title="root">{{ root }}</div>

    <NScrollbar class="tree-scroll">
      <div v-if="!workingDir" class="empty-hint">
        <NEmpty description="此会话未设置工作目录" size="small" />
      </div>
      <div v-else-if="loading && !nodes.length" class="loading-hint">
        <NSpin size="small" />
      </div>
      <div v-else-if="!nodes.length" class="empty-hint">
        <NEmpty description="空目录" size="small" />
      </div>
      <template v-else>
        <FileTreeNode
          v-for="node in nodes"
          :key="node.path"
          :node="node"
          :depth="0"
          :expanded="expanded"
          :loading-paths="loadingPaths"
          :children-by-path="childrenByPath"
          @toggle="onNodeClick"
        />
      </template>
    </NScrollbar>
  </div>
</template>

<style scoped>
.file-tree-panel {
  width: 260px;
  min-width: 220px;
  border-left: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}
.file-tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
  border-bottom: 1px solid #f0f0f0;
}
.header-label {
  font-weight: 600;
  font-size: 13px;
  color: #333;
}
.root-path {
  padding: 4px 12px;
  font-size: 11px;
  color: #999;
  font-family: 'SF Mono', 'Monaco', monospace;
  border-bottom: 1px solid #f0f0f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-scroll {
  flex: 1;
  padding: 6px 0;
}
.empty-hint,
.loading-hint {
  padding: 40px 12px;
  text-align: center;
}
</style>
