import { marked } from 'marked'
import DOMPurify from 'dompurify'

/**
 * Markdown → 安全 HTML。
 * breaks: 单个换行也渲染为换行（笔记场景更符合直觉）；
 * DOMPurify 兜底防 XSS（数据虽是本地的，渲染层仍不做信任假设）。
 */
export function renderMarkdown(src: string | null | undefined): string {
  if (!src?.trim()) return ''
  const html = marked.parse(src, { async: false, gfm: true, breaks: true })
  return DOMPurify.sanitize(html)
}

/**
 * Markdown → 纯文本（渲染后提取 textContent）。
 * 用于单行场景（索引标题/摘要）：去掉 ##、** 等语法符号，只留干净文字。
 */
export function markdownToText(src: string | null | undefined): string {
  if (!src?.trim()) return ''
  const el = document.createElement('div')
  el.innerHTML = renderMarkdown(src)
  return (el.textContent ?? '').replace(/\s+/g, ' ').trim()
}