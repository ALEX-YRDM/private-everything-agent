/**
 * 把 edit_file / multi_edit 这类"精确字符串替换"工具的 args
 * 合成为一份可交给 <DiffView> 渲染的伪 unified diff 文本。
 *
 * 因为我们只有 old_string / new_string 而拿不到完整文件，无法
 * 生成真正 hunk 行号，这里用 @@ -1,N +1,M @@ 占位。
 * 这份产物给用户看变更足够清晰，不用于 apply。
 */
export function buildDiffFromEdit(oldStr: string, newStr: string): string {
  const oldLines = oldStr.split('\n')
  const newLines = newStr.split('\n')
  const header = `@@ -1,${oldLines.length} +1,${newLines.length} @@`
  const delBlock = oldLines.map((l) => `-${l}`).join('\n')
  const addBlock = newLines.map((l) => `+${l}`).join('\n')
  return `${header}\n${delBlock}\n${addBlock}`
}

/**
 * multi_edit 的 edits 数组 → 拼成一份多 hunk 的 diff
 */
export function buildDiffFromMultiEdit(
  edits: Array<{ old_string: string; new_string: string; replace_all?: boolean }>,
): string {
  return edits
    .map((e) => buildDiffFromEdit(e.old_string ?? '', e.new_string ?? ''))
    .join('\n')
}

/**
 * 根据工具名 + args 推断该展示什么。
 * 返回 null 表示走默认 fallback。
 */
export interface DiffPreview {
  kind: 'diff'
  patch: string
}
export interface CodePreview {
  kind: 'code'
  code: string
  filename?: string
  lang?: string
}

export function pickToolPreview(
  toolName: string,
  args: Record<string, any> | undefined,
): DiffPreview | CodePreview | null {
  if (!args) return null

  const path =
    typeof args.path === 'string'
      ? args.path
      : typeof args.file_path === 'string'
      ? args.file_path
      : undefined

  // edit_file: old_string + new_string
  if (toolName === 'edit_file' &&
      typeof args.old_string === 'string' &&
      typeof args.new_string === 'string') {
    const header = path ? `--- a/${path}\n+++ b/${path}\n` : ''
    return { kind: 'diff', patch: header + buildDiffFromEdit(args.old_string, args.new_string) }
  }

  // multi_edit: edits 数组
  if (toolName === 'multi_edit' && Array.isArray(args.edits)) {
    const header = path ? `--- a/${path}\n+++ b/${path}\n` : ''
    return { kind: 'diff', patch: header + buildDiffFromMultiEdit(args.edits) }
  }

  // apply_patch: 直接取 patch
  if (toolName === 'apply_patch' && typeof args.patch === 'string') {
    return { kind: 'diff', patch: args.patch }
  }

  // write_file: content 按扩展名高亮
  if (toolName === 'write_file' && typeof args.content === 'string') {
    return { kind: 'code', code: args.content, filename: path }
  }

  // exec: command 用 bash 高亮
  if (toolName === 'exec' && typeof args.command === 'string') {
    return { kind: 'code', code: args.command, lang: 'bash' }
  }

  // read_file 之类：交给结果区
  return null
}
