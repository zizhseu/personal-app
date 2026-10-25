import dayjs from 'dayjs'
import { QA_STATUS_LABELS, sortTags } from './constants'
import { renderMarkdown } from '@/shared/utils/markdown'
import type { QaItem } from './types'

/** 分类导出的 Markdown 文档（题目原样保留 Markdown） */
export function buildCategoryMarkdown(categoryName: string, items: QaItem[]): string {
  const lines: string[] = [
    `# ${categoryName}`,
    '',
    `> 共 ${items.length} 条题目 · 导出时间 ${dayjs().format('YYYY-MM-DD HH:mm')}`,
    '',
  ]
  items.forEach((item, idx) => {
    lines.push('---', '')
    lines.push(`## ${idx + 1}. ${item.question.trim()}`, '')
    const meta: string[] = []
    if (item.tags?.length) meta.push(`**标签**：${sortTags(item.tags).join('、')}`)
    meta.push(`**状态**：${QA_STATUS_LABELS[item.status]}`)
    lines.push(meta.join(' · '), '')
    if (item.answer?.trim()) {
      lines.push('### 答案', '', item.answer.trim(), '')
    }
  })
  return lines.join('\n')
}

function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** 导出 Markdown 文件 */
export function exportCategoryMarkdown(categoryName: string, items: QaItem[]): void {
  downloadTextFile(`${categoryName}-面试问答.md`, buildCategoryMarkdown(categoryName, items))
}

const PRINT_STYLE = `
  @page { size: A4; margin: 16mm 14mm; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 24px 28px;
    font: 14px/1.75 "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
    color: #1f2328;
  }
  h1 { font-size: 22px; margin: 0 0 6px; }
  .doc-sub { color: #6b7280; font-size: 12.5px; margin-bottom: 18px; }
  .qa-item { padding: 14px 0 18px; border-bottom: 1px solid #e5e7eb; }
  .qa-item + .qa-item { break-inside: auto; }
  .q-line { display: flex; gap: 10px; align-items: flex-start; break-after: avoid; }
  .q-badge {
    flex-shrink: 0; margin-top: 2px; padding: 1px 7px; border-radius: 5px;
    background: #eef2ff; color: #4f46e5; font-size: 12px; font-weight: 700;
  }
  .q-text { font-weight: 700; font-size: 15px; }
  .q-text p, .a-text p { margin: 0 0 8px; }
  .q-meta { margin: 6px 0 10px 44px; color: #6b7280; font-size: 12px; }
  .a-text { margin-left: 44px; }
  .a-text h1, .a-text h2, .a-text h3, .a-text h4 { font-size: 14px; margin: 10px 0 6px; }
  .a-text ul, .a-text ol { margin: 4px 0 8px; padding-left: 22px; }
  .a-text code {
    background: #f3f4f6; padding: 1px 5px; border-radius: 4px;
    font-family: Consolas, "Courier New", monospace; font-size: 12.5px;
  }
  .a-text pre {
    background: #f8f9fb; border: 1px solid #e5e7eb; border-radius: 8px;
    padding: 10px 12px; overflow-x: auto; break-inside: avoid;
  }
  .a-text pre code { background: none; padding: 0; }
  .a-text table { border-collapse: collapse; margin: 8px 0; }
  .a-text th, .a-text td { border: 1px solid #e5e7eb; padding: 5px 9px; }
  .a-text blockquote {
    margin: 8px 0; padding: 2px 12px; border-left: 3px solid #d1d5db; color: #6b7280;
  }
  @media print {
    body { padding: 0; }
    .qa-item { break-inside: avoid; }
    .a-text pre { break-inside: avoid; }
  }
`

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 导出 PDF：打开排版好的打印视图，浏览器「另存为 PDF」（中文与长文档渲染最稳） */
export function exportCategoryPdf(categoryName: string, items: QaItem[]): void {
  const win = window.open('', '_blank')
  if (!win) {
    throw new Error('浏览器拦截了弹窗，请允许本站弹窗后重试')
  }
  const safeName = escapeHtml(categoryName)
  const sections = items
    .map((item, idx) => {
      const meta: string[] = []
      if (item.tags?.length) meta.push(`标签：${sortTags(item.tags).join('、')}`)
      meta.push(`状态：${QA_STATUS_LABELS[item.status]}`)
      const answer = item.answer?.trim()
        ? `<div class="a-text">${renderMarkdown(item.answer)}</div>`
        : ''
      return `
        <section class="qa-item">
          <div class="q-line">
            <span class="q-badge">Q${idx + 1}</span>
            <div class="q-text">${renderMarkdown(item.question)}</div>
          </div>
          <div class="q-meta">${meta.join(' · ')}</div>
          ${answer}
        </section>`
    })
    .join('')

  win.document.open()
  win.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${safeName}-面试问答</title>
  <style>${PRINT_STYLE}</style>
</head>
<body>
  <h1>${safeName}</h1>
  <div class="doc-sub">共 ${items.length} 条题目 · 导出时间 ${dayjs().format('YYYY-MM-DD HH:mm')}</div>
  ${sections}
  <script>setTimeout(function () { window.focus(); window.print(); }, 300);</script>
</body>
</html>`)
  win.document.close()
}
