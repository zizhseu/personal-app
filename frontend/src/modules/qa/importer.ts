/**
 * 面试八股笔记导入解析器。
 *
 * 格式约定（见 docs/learning/01-context.md）：
 * - `## ` 开头的行 = 一道题目（标题行去掉常见编号前缀后作为问题）
 * - 该行之后到下一个 `## ` 之间的内容 = 答案要点（保留 Markdown 原文）
 * - ``` / ~~~ 围栏代码块内的所有行归属当前题目答案（代码块里可能出现行首 ##）
 * - `# ` 一级标题与第一个 `## ` 之前的说明文字忽略
 */

export interface ParsedQa {
  question: string
  answer: string | null
}

/** 剥离常见编号前缀：Q1： / Q1 · / Q1、 / 1. 等 */
function stripQuestionPrefix(text: string): string {
  return text
    .replace(/^Q\s*\d+\s*[·・．.：:、]?\s*/i, '')
    .replace(/^\d+\s*[：:、.]\s*/, '')
    .trim()
}

export function parseQaMarkdown(content: string): ParsedQa[] {
  const items: ParsedQa[] = []
  let current: ParsedQa | null = null
  let inCodeBlock = false

  const appendAnswer = (line: string) => {
    if (!current) return
    current.answer = current.answer === null ? line : current.answer + '\n' + line
  }

  for (const raw of content.split(/\r?\n/)) {
    const line = raw.trimEnd()
    // 围栏代码块开关：块内所有行（含行首 ##）归属当前题目
    if (/^\s*(```|~~~)/.test(line)) {
      inCodeBlock = !inCodeBlock
      appendAnswer(line)
      continue
    }
    if (inCodeBlock) {
      appendAnswer(line)
      continue
    }
    if (/^##\s+/.test(line)) {
      if (current) items.push(current)
      current = { question: stripQuestionPrefix(line.replace(/^##\s+/, '')), answer: null }
    } else if (/^#\s+/.test(line)) {
      continue // 一级标题（文档名）忽略
    } else if (current) {
      appendAnswer(line)
    }
    // 第一个 ## 之前的说明文字忽略
  }
  if (current) items.push(current)

  return items
    .map((i) => ({ ...i, answer: i.answer?.trim() ? i.answer : null }))
    .filter((i) => i.question.trim().length > 0)
}