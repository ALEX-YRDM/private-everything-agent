import { marked } from 'marked'
import hljs from 'highlight.js'

marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderer = new marked.Renderer()

renderer.code = ({ text, lang }: { text: string; lang?: string }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(text, { language }).value
  return `<pre class="code-block"><code class="hljs language-${language}">${highlighted}</code></pre>`
}

marked.use({ renderer })

export function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked(content) as string
}
