/**
 * Clipboard utility for copying text content with HTML formatting support
 */

export async function copyToClipboard(
  text: string,
  html?: string,
  onSuccess?: () => void,
  onError?: (error: Error) => void
): Promise<void> {
  try {
    // Modern Clipboard API with rich text support
    if (navigator.clipboard && window.ClipboardItem) {
      const items: Record<string, Blob> = {
        'text/plain': new Blob([text], { type: 'text/plain' }),
      }

      if (html) {
        items['text/html'] = new Blob([html], { type: 'text/html' })
      }

      await navigator.clipboard.write([new ClipboardItem(items)])
      onSuccess?.()
    } else {
      // Fallback for older browsers
      await fallbackCopyToClipboard(text)
      onSuccess?.()
    }
  } catch (error) {
    onError?.(error as Error)
  }
}

/**
 * Fallback for browsers that don't support the modern Clipboard API
 */
function fallbackCopyToClipboard(text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.left = '-9999px'
    textArea.style.top = '-9999px'

    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()

    try {
      document.execCommand('copy')
      document.body.removeChild(textArea)
      resolve()
    } catch (error) {
      document.body.removeChild(textArea)
      reject(error)
    }
  })
}

/**
 * Convert HTML to plain text (basic implementation)
 */
export function htmlToPlainText(html: string): string {
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || div.innerText || ''
}
