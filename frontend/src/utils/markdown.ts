import { marked } from 'marked'
import hljs from './hljs'

marked.setOptions({
  breaks: true,
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

marked.use({ renderer })

export function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked(content) as string
}
