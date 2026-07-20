<script setup lang="ts">
import { computed, ref } from 'vue'
import hljs from 'highlight.js'
import { copyToClipboard } from '../utils/clipboard'
import { useMessage } from 'naive-ui'

const props = defineProps<{
  code: string
  lang?: string
  filename?: string
  maxHeight?: string  // 默认 340px
}>()

const msg = useMessage()
const copied = ref(false)

/** 根据扩展名推断语言 */
function langFromFilename(name: string | undefined): string | undefined {
  if (!name) return
  const ext = name.split('.').pop()?.toLowerCase()
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript',
    js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript',
    py: 'python',
    vue: 'xml',
    md: 'markdown', markdown: 'markdown',
    yml: 'yaml', yaml: 'yaml',
    toml: 'ini',
    sh: 'bash', bash: 'bash', zsh: 'bash',
    json: 'json',
    css: 'css', scss: 'scss',
    html: 'xml', htm: 'xml', svg: 'xml',
    go: 'go', rs: 'rust', java: 'java',
    c: 'c', h: 'c', cpp: 'cpp', hpp: 'cpp',
    sql: 'sql',
    dockerfile: 'dockerfile',
  }
  return ext ? map[ext] : undefined
}

const resolvedLang = computed(() => {
  const l = props.lang || langFromFilename(props.filename)
  return l && hljs.getLanguage(l) ? l : 'plaintext'
})

const highlighted = computed(() => {
  try {
    return hljs.highlight(props.code, { language: resolvedLang.value }).value
  } catch {
    return props.code.replace(/[&<>]/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] || c),
    )
  }
})

async function copy() {
  await copyToClipboard(
    props.code,
    undefined,
    () => {
      msg.success('代码已复制')
      copied.value = true
      setTimeout(() => (copied.value = false), 1200)
    },
    (e) => msg.error(`复制失败: ${e.message}`),
  )
}
</script>

<template>
  <div class="cb-wrap" :style="{ '--cb-max-h': maxHeight || '340px' }">
    <div class="cb-header" v-if="filename || resolvedLang !== 'plaintext'">
      <span v-if="filename" class="cb-filename">{{ filename }}</span>
      <span v-else class="cb-lang">{{ resolvedLang }}</span>
      <button class="cb-copy" :class="{ copied }" @click="copy" title="复制">
        {{ copied ? '✅' : '📋' }}
      </button>
    </div>
    <pre class="cb-pre"><code class="hljs" :class="`language-${resolvedLang}`" v-html="highlighted" /></pre>
    <button v-if="!filename && resolvedLang === 'plaintext'" class="cb-copy floating" :class="{ copied }" @click="copy" title="复制">
      {{ copied ? '✅' : '📋' }}
    </button>
  </div>
</template>

<style scoped>
.cb-wrap {
  position: relative;
  margin: 6px 0;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #2a2a2a;
}

.cb-header {
  display: flex;
  align-items: center;
  padding: 4px 8px 4px 12px;
  background: #2a2a2a;
  border-bottom: 1px solid #3a3a3a;
  font-size: 11px;
  color: #a0a0a0;
}
.cb-filename {
  font-family: 'SF Mono', 'Monaco', monospace;
  color: #d4d4d4;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cb-lang {
  flex: 1;
  color: #9ca3af;
  font-family: 'SF Mono', 'Monaco', monospace;
  text-transform: lowercase;
}

.cb-copy {
  background: rgba(255, 255, 255, 0.05);
  color: #d4d4d4;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
  flex-shrink: 0;
}
.cb-copy:hover { background: rgba(255, 255, 255, 0.15); }
.cb-copy.copied {
  background: rgba(82, 196, 26, 0.35);
  border-color: rgba(82, 196, 26, 0.6);
}
.cb-copy.floating {
  position: absolute;
  top: 6px;
  right: 6px;
  opacity: 0;
  transition: opacity 0.15s;
}
.cb-wrap:hover .cb-copy.floating { opacity: 1; }

.cb-pre {
  margin: 0;
  padding: 10px 12px;
  overflow: auto;
  max-height: var(--cb-max-h);
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  font-size: 12.5px;
  line-height: 1.55;
  color: #d4d4d4;
}
.cb-pre code {
  background: transparent;
  padding: 0;
  color: inherit;
  font-size: inherit;
}
</style>
