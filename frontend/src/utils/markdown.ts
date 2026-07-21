import { marked } from 'marked'
import hljs from './hljs'

marked.setOptions({
  // breaks:false 让软换行不再变 <br>，段落内的中文换行不会撕碎
  // 想强制换行的场景仍可写两个空格 + 换行，或空行分段
  breaks: false,
  gfm: true,
})

const renderer = new marked.Renderer()

renderer.code = ({ text, lang }: { text: string; lang?: string }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(text, { language }).value
  return `<div class="code-block-wrapper">`
    + `<pre class="code-block"><code class="hljs language-${language}">${highlighted}</code></pre>`
    + `<button class="code-copy-btn" type="button" title="复制代码">📋</button>`
    + `</div>`
}

// 图片：加 lazy loading + max-width 兜底，避免超宽图撑破气泡
renderer.image = ({ href, title, text }: { href: string; title?: string | null; text: string }) => {
  const titleAttr = title ? ` title="${title.replace(/"/g, '&quot;')}"` : ''
  const alt = (text || '').replace(/"/g, '&quot;')
  return `<img class="md-image" loading="lazy" src="${href}" alt="${alt}"${titleAttr} />`
}

marked.use({ renderer })

export function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked(content) as string
}
