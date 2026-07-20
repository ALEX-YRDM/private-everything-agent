<script setup lang="ts">
import { computed, ref } from 'vue'
import { copyToClipboard } from '../utils/clipboard'
import { useMessage } from 'naive-ui'

const props = defineProps<{
  patch: string
  maxHeight?: string
}>()

const msg = useMessage()
const copied = ref(false)

interface Line {
  kind: 'add' | 'del' | 'ctx' | 'hunk' | 'meta'
  content: string
  oldNo?: number
  newNo?: number
}

/** 解析 unified diff：把 `@@ -a,b +c,d @@` 里的行号推进赋给每一行 */
const lines = computed<Line[]>(() => {
  const raw = props.patch || ''
  const result: Line[] = []
  let oldNo = 0
  let newNo = 0

  for (const line of raw.split('\n')) {
    if (line.startsWith('@@')) {
      const m = /@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line)
      if (m) {
        oldNo = parseInt(m[1]!, 10)
        newNo = parseInt(m[2]!, 10)
      }
      result.push({ kind: 'hunk', content: line })
    } else if (line.startsWith('+++') || line.startsWith('---') ||
               line.startsWith('diff ') || line.startsWith('index ')) {
      result.push({ kind: 'meta', content: line })
    } else if (line.startsWith('+') && !line.startsWith('+++')) {
      result.push({ kind: 'add', content: line.slice(1), newNo })
      newNo++
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      result.push({ kind: 'del', content: line.slice(1), oldNo })
      oldNo++
    } else {
      result.push({ kind: 'ctx', content: line.replace(/^ /, ''), oldNo, newNo })
      oldNo++
      newNo++
    }
  }
  return result
})

const stats = computed(() => {
  let add = 0, del = 0
  for (const l of lines.value) {
    if (l.kind === 'add') add++
    else if (l.kind === 'del') del++
  }
  return { add, del }
})

async function copyRaw() {
  await copyToClipboard(
    props.patch,
    undefined,
    () => {
      msg.success('补丁已复制')
      copied.value = true
      setTimeout(() => (copied.value = false), 1200)
    },
    (e) => msg.error(`复制失败: ${e.message}`),
  )
}
</script>

<template>
  <div class="dv-wrap" :style="{ '--dv-max-h': maxHeight || '380px' }">
    <div class="dv-header">
      <span class="dv-title">📝 Diff</span>
      <span class="dv-stat add">+{{ stats.add }}</span>
      <span class="dv-stat del">-{{ stats.del }}</span>
      <span class="dv-spacer" />
      <button class="dv-copy" :class="{ copied }" @click="copyRaw" title="复制原始 patch">
        {{ copied ? '✅' : '📋' }}
      </button>
    </div>
    <div class="dv-body">
      <div
        v-for="(l, i) in lines"
        :key="i"
        class="dv-line"
        :class="`kind-${l.kind}`"
      >
        <span class="dv-lineno old">{{ l.kind === 'add' || l.kind === 'hunk' || l.kind === 'meta' ? '' : (l.oldNo ?? '') }}</span>
        <span class="dv-lineno new">{{ l.kind === 'del' || l.kind === 'hunk' || l.kind === 'meta' ? '' : (l.newNo ?? '') }}</span>
        <span class="dv-sign">{{
          l.kind === 'add' ? '+' :
          l.kind === 'del' ? '-' :
          l.kind === 'hunk' ? '' :
          l.kind === 'meta' ? '' : ' '
        }}</span>
        <span class="dv-content">{{ l.content }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dv-wrap {
  margin: 6px 0;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #2a2a2a;
}

.dv-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 12px;
  background: #2a2a2a;
  border-bottom: 1px solid #3a3a3a;
  font-size: 11px;
}
.dv-title {
  color: #d4d4d4;
  font-weight: 500;
}
.dv-stat {
  font-family: 'SF Mono', monospace;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
}
.dv-stat.add { background: rgba(46, 160, 67, 0.25); color: #56d364; }
.dv-stat.del { background: rgba(248, 81, 73, 0.2); color: #f78166; }
.dv-spacer { flex: 1; }

.dv-copy {
  background: rgba(255, 255, 255, 0.05);
  color: #d4d4d4;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  cursor: pointer;
}
.dv-copy:hover { background: rgba(255, 255, 255, 0.15); }
.dv-copy.copied {
  background: rgba(82, 196, 26, 0.35);
  border-color: rgba(82, 196, 26, 0.6);
}

.dv-body {
  max-height: var(--dv-max-h);
  overflow: auto;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.55;
}

.dv-line {
  display: flex;
  align-items: flex-start;
  gap: 0;
  padding: 0 4px 0 0;
  min-height: 18px;
  white-space: pre;
}
.dv-line.kind-add { background: rgba(46, 160, 67, 0.13); }
.dv-line.kind-del { background: rgba(248, 81, 73, 0.13); }
.dv-line.kind-hunk {
  background: #223;
  color: #7aa2f7;
  padding-left: 10px;
}
.dv-line.kind-meta {
  color: #6b7280;
  padding-left: 10px;
  font-style: italic;
}

.dv-lineno {
  flex-shrink: 0;
  width: 40px;
  padding: 0 6px 0 4px;
  color: #6b7280;
  text-align: right;
  font-size: 11px;
  border-right: 1px solid #2a2a2a;
  user-select: none;
}
.dv-lineno.new { border-right: none; }
.dv-line.kind-hunk .dv-lineno,
.dv-line.kind-meta .dv-lineno { display: none; }

.dv-sign {
  flex-shrink: 0;
  width: 14px;
  text-align: center;
  color: #6b7280;
  user-select: none;
}
.dv-line.kind-add .dv-sign { color: #56d364; }
.dv-line.kind-del .dv-sign { color: #f78166; }

.dv-content {
  flex: 1;
  color: #d4d4d4;
  white-space: pre;
  padding-left: 4px;
  overflow-wrap: normal;
}
.dv-line.kind-hunk .dv-content { color: #7aa2f7; }
.dv-line.kind-meta .dv-content { color: #6b7280; }
</style>
