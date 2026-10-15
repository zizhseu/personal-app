import request from '@/shared/api/request'
import type { ParsedQuiz, QuizCategory, QuizItem, QuizPayload } from './types'

/** quiz 模块全部接口调用 */

export function fetchCategories(): Promise<QuizCategory[]> {
  return request.get('/quiz/categories') as Promise<QuizCategory[]>
}

export function createCategory(name: string): Promise<QuizCategory> {
  return request.post('/quiz/categories', { name }) as Promise<QuizCategory>
}

export function renameCategory(id: number, name: string): Promise<QuizCategory> {
  return request.put(`/quiz/categories/${id}`, { name }) as Promise<QuizCategory>
}

export function deleteCategory(id: number): Promise<void> {
  return request.delete(`/quiz/categories/${id}`) as Promise<void>
}

export function fetchItems(): Promise<QuizItem[]> {
  return request.get('/quiz/items') as Promise<QuizItem[]>
}

export function createItem(payload: QuizPayload): Promise<QuizItem> {
  return request.post('/quiz/items', payload) as Promise<QuizItem>
}

export function updateItem(id: number, payload: Partial<QuizPayload>): Promise<QuizItem> {
  return request.put(`/quiz/items/${id}`, payload) as Promise<QuizItem>
}

export function deleteItem(id: number): Promise<void> {
  return request.delete(`/quiz/items/${id}`) as Promise<void>
}

/** AI 解析导入：原文 → 候选题目列表（不入库） */
export function parseQuiz(text: string): Promise<{ questions: ParsedQuiz[] }> {
  return request.post('/quiz/parse', { text }) as Promise<{ questions: ParsedQuiz[] }>
}