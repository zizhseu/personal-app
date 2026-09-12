import request from '@/shared/api/request'
import type { QaCategoryEntity, QaItem, QaPayload, QaStatus } from './types'

/** qa 模块全部接口调用 */

// ---------- 分类 ----------

export function fetchCategories(): Promise<QaCategoryEntity[]> {
  return request.get('/qa/categories') as Promise<QaCategoryEntity[]>
}

export function createCategory(name: string): Promise<QaCategoryEntity> {
  return request.post('/qa/categories', { name }) as Promise<QaCategoryEntity>
}

export function renameCategory(id: number, name: string): Promise<QaCategoryEntity> {
  return request.put(`/qa/categories/${id}`, { name }) as Promise<QaCategoryEntity>
}

export function deleteCategory(id: number): Promise<void> {
  return request.delete(`/qa/categories/${id}`) as Promise<void>
}

// ---------- 题目 ----------

export function fetchItems(): Promise<QaItem[]> {
  return request.get('/qa/items') as Promise<QaItem[]>
}

export function createItem(payload: QaPayload): Promise<QaItem> {
  return request.post('/qa/items', payload) as Promise<QaItem>
}

export function updateItem(id: number, payload: Partial<QaPayload>): Promise<QaItem> {
  return request.put(`/qa/items/${id}`, payload) as Promise<QaItem>
}

export function patchStatus(id: number, status: QaStatus): Promise<QaItem> {
  return request.patch(`/qa/items/${id}/status`, { status }) as Promise<QaItem>
}

export function markRead(id: number): Promise<QaItem> {
  return request.patch(`/qa/items/${id}/read`) as Promise<QaItem>
}

export function deleteItem(id: number): Promise<void> {
  return request.delete(`/qa/items/${id}`) as Promise<void>
}