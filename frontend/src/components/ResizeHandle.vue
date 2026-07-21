<script setup lang="ts">
import { ref, onUnmounted, computed } from 'vue'

const props = defineProps<{
  /**
   * handle 位于当前面板的哪一侧
   * - x 轴（列宽调整，默认）：'left' | 'right'
   * - y 轴（行高调整）：'top' | 'bottom'
   */
  side: 'left' | 'right' | 'top' | 'bottom'
  disabled?: boolean
  /** 拖拽轴：x 调宽度、y 调高度。默认根据 side 自动推断，也可显式指定 */
  axis?: 'x' | 'y'
}>()

const emit = defineEmits<{
  'resize-start': []
  /** 相对拖拽开始的位移；x 轴是 deltaX，y 轴是 deltaY。调用方自己截取 */
  resize: [delta: number]
  'resize-end': []
}>()

const dragging = ref(false)
let start = 0

const effectiveAxis = computed<'x' | 'y'>(() =>
  props.axis ?? ((props.side === 'top' || props.side === 'bottom') ? 'y' : 'x'),
)

const cursorClass = computed(() =>
  effectiveAxis.value === 'y' ? 'cursor-row-resize' : 'cursor-col-resize',
)

function onPointerDown(e: PointerEvent) {
  if (props.disabled) return
  e.preventDefault()
  dragging.value = true
  start = effectiveAxis.value === 'y' ? e.clientY : e.clientX
  ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
  document.body.classList.add(cursorClass.value)
  document.addEventListener('pointermove', onMove)
  document.addEventListener('pointerup', onUp, { once: true })
  emit('resize-start')
}

function onMove(e: PointerEvent) {
  if (!dragging.value) return
  const cur = effectiveAxis.value === 'y' ? e.clientY : e.clientX
  emit('resize', cur - start)
}

function onUp() {
  dragging.value = false
  document.body.classList.remove('cursor-col-resize', 'cursor-row-resize')
  document.removeEventListener('pointermove', onMove)
  emit('resize-end')
}

onUnmounted(() => {
  document.body.classList.remove('cursor-col-resize', 'cursor-row-resize')
  document.removeEventListener('pointermove', onMove)
})
</script>

<template>
  <div
    class="resize-handle"
    :class="[`side-${side}`, `axis-${effectiveAxis}`, { dragging, disabled }]"
    @pointerdown="onPointerDown"
  >
    <div class="handle-visual" />
  </div>
</template>

<style scoped>
.resize-handle {
  position: absolute;
  z-index: 10;
  user-select: none;
}
/* x 轴：竖条 handle，横向拖 */
.resize-handle.axis-x {
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
}
.resize-handle.side-left { right: -3px; }
.resize-handle.side-right { left: -3px; }

/* y 轴：横条 handle，纵向拖 */
.resize-handle.axis-y {
  left: 0;
  right: 0;
  height: 6px;
  cursor: row-resize;
}
.resize-handle.side-top { top: -3px; }
.resize-handle.side-bottom { bottom: -3px; }

.resize-handle.disabled { cursor: default; pointer-events: none; }

.handle-visual {
  position: absolute;
  background: transparent;
  transition: background 0.15s;
}
.axis-x .handle-visual {
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
}
.axis-y .handle-visual {
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  transform: translateY(-50%);
}

.resize-handle:hover .handle-visual,
.resize-handle.dragging .handle-visual {
  background: #1677ff;
}
.axis-x:hover .handle-visual,
.axis-x.dragging .handle-visual { width: 2px; }
.axis-y:hover .handle-visual,
.axis-y.dragging .handle-visual { height: 2px; }
</style>

<style>
body.cursor-col-resize,
body.cursor-col-resize * {
  cursor: col-resize !important;
}
body.cursor-row-resize,
body.cursor-row-resize * {
  cursor: row-resize !important;
}
</style>
