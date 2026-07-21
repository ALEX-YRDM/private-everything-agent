<script setup lang="ts">
/**
 * 输入区上方的三条附件条：@ 引用路径 chip / 图片缩略图 / 文件条。
 * 纯展示组件——数据和事件都通过 props / emit 传，避免和 ChatPanel 状态直接耦合。
 */
export interface AttachedFileInfo {
  name: string
  size?: number
}

defineProps<{
  paths: string[]           // @ 引用的路径 chip
  images: string[]          // dataURL 或 blob URL 数组
  files: AttachedFileInfo[]
}>()

const emit = defineEmits<{
  'remove-path': [path: string]
  'clear-paths': []
  'remove-image': [index: number]
  'remove-file': [index: number]
}>()

/** chip 显示用：目录 + 文件名，太长时截断中间 */
function shortPath(p: string): string {
  if (p.length <= 42) return p
  const parts = p.split('/')
  const last = parts.pop() || p
  return `…/${last}`
}
</script>

<template>
  <!-- @ 引用附件 chip 条（发一次消费一次） -->
  <div v-if="paths.length" class="pending-attachments">
    <div class="pa-label">📎 附加到本条：</div>
    <div class="pa-chips">
      <span
        v-for="p in paths"
        :key="p"
        class="pa-chip"
        :title="p"
      >
        <span class="pa-chip-name">{{ shortPath(p) }}</span>
        <button class="pa-chip-x" @click="emit('remove-path', p)" title="移除">✕</button>
      </span>
      <button class="pa-clear" @click="emit('clear-paths')">清空</button>
    </div>
  </div>

  <!-- 图片预览 -->
  <div v-if="images.length" class="attached-images">
    <div v-for="(img, idx) in images" :key="idx" class="attached-image-item">
      <img :src="img" class="attached-thumb" />
      <button class="remove-image-btn" @click="emit('remove-image', idx)">✕</button>
    </div>
  </div>

  <!-- 文件附件 -->
  <div v-if="files.length" class="attached-files">
    <div v-for="(file, idx) in files" :key="idx" class="attached-file-item">
      <span class="file-name">📎 {{ file.name }}</span>
      <button class="remove-file-btn" @click="emit('remove-file', idx)">✕</button>
    </div>
  </div>
</template>

<style scoped>
/* pending @ 路径 */
.pending-attachments {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 10px;
  background: var(--md-brand-soft);
  border: 1px dashed var(--md-brand);
  border-radius: 8px;
  font-size: 12px;
  color: var(--md-brand-strong);
}
.pa-label {
  flex-shrink: 0;
  font-weight: 500;
  color: var(--md-brand);
  padding-top: 3px;
}
.pa-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.pa-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px 2px 8px;
  background: var(--md-bg);
  border: 1px solid var(--md-brand);
  border-radius: 12px;
  font-family: var(--md-font-mono);
  font-size: 11px;
  color: var(--md-brand-strong);
  max-width: 260px;
}
.pa-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pa-chip-x {
  border: none;
  background: transparent;
  color: var(--md-text-muted);
  cursor: pointer;
  padding: 0 2px;
  font-size: 11px;
  line-height: 1;
  border-radius: 3px;
}
.pa-chip-x:hover { background: var(--md-danger-soft); color: var(--md-danger); }
.pa-clear {
  border: none;
  background: transparent;
  color: var(--md-text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
}
.pa-clear:hover { color: var(--md-danger); }

/* 图片 */
.attached-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.attached-image-item {
  position: relative;
  width: 68px;
  height: 68px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--md-border);
}
.attached-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.remove-image-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: var(--md-danger);
  color: white;
  font-size: 12px;
  line-height: 22px;
  text-align: center;
  cursor: pointer;
  padding: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

/* 文件 */
.attached-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.attached-file-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: var(--md-bg-muted);
  border: 1px solid var(--md-border);
  border-radius: 6px;
  font-size: 12px;
  color: var(--md-text-primary);
}
.file-name {
  font-family: var(--md-font-mono);
}
.remove-file-btn {
  border: none;
  background: transparent;
  color: var(--md-text-muted);
  cursor: pointer;
  padding: 0 2px;
  font-size: 11px;
  border-radius: 3px;
}
.remove-file-btn:hover { color: var(--md-danger); background: var(--md-danger-soft); }
</style>
