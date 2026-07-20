<script setup lang="ts">
import { ref, onUnmounted } from 'vue'

const props = defineProps<{
  side: 'left' | 'right'  // handle 位于当前面板的哪一侧；决定拖拽方向
  disabled?: boolean
}>()

const emit = defineEmits<{
  'resize-start': []
  resize: [deltaX: number]  // 相对拖拽开始的位移；调用方自己截取
  'resize-end': []
}>()

const dragging = ref(false)
let startX = 0

function onPointerDown(e: PointerEvent) {
  if (props.disabled) return
  e.preventDefault()
  dragging.value = true
  startX = e.clientX
  ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
  document.body.classList.add('cursor-col-resize')
  document.addEventListener('pointermove', onMove)
  document.addEventListener('pointerup', onUp, { once: true })
  emit('resize-start')
}

function onMove(e: PointerEvent) {
  if (!dragging.value) return
  emit('resize', e.clientX - startX)
}

function onUp() {
  dragging.value = false
  document.body.classList.remove('cursor-col-resize')
  document.removeEventListener('pointermove', onMove)
  emit('resize-end')
}

onUnmounted(() => {
  document.body.classList.remove('cursor-col-resize')
  document.removeEventListener('pointermove', onMove)
})
</script>

<template>
  <div
    class="resize-handle"
    :class="[`side-${side}`, { dragging, disabled }]"
    @pointerdown="onPointerDown"
  >
    <div class="handle-visual" />
  </div>
</template>

<style scoped>
.resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
  z-index: 10;
  user-select: none;
}
.resize-handle.side-left { right: -3px; }
.resize-handle.side-right { left: -3px; }
.resize-handle.disabled { cursor: default; pointer-events: none; }

.handle-visual {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  background: transparent;
  transform: translateX(-50%);
  transition: background 0.15s;
}
.resize-handle:hover .handle-visual,
.resize-handle.dragging .handle-visual {
  background: #1677ff;
  width: 2px;
}
</style>

<style>
body.cursor-col-resize,
body.cursor-col-resize * {
  cursor: col-resize !important;
}
</style>
