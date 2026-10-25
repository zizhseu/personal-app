import request from '@/shared/api/request'
import type { CodingCategory, CodingItem, CodingPayload, CodingStatus, CodingSummary } from './types'

export const fetchCategories = () => request.get('/coding/categories') as Promise<CodingCategory[]>
export const createCategory = (name: string) => request.post('/coding/categories', { name }) as Promise<CodingCategory>
export const renameCategory = (id: number, name: string) => request.put(`/coding/categories/${id}`, { name }) as Promise<CodingCategory>
export const deleteCategory = (id: number) => request.delete(`/coding/categories/${id}`)
export const fetchItems = () => request.get('/coding/items') as Promise<CodingSummary[]>
export const fetchItem = (id: number) => request.get(`/coding/items/${id}`) as Promise<CodingItem>
export const saveItem = (data: CodingPayload, id?: number, silent = false) => (id === undefined
  ? request.post('/coding/items', data, { silentError: silent })
  : request.put(`/coding/items/${id}`, data, { silentError: silent })) as Promise<CodingItem>
export const patchStatus = (id: number, status: CodingStatus) => request.patch(`/coding/items/${id}/status`, { status }) as Promise<CodingItem>
export const deleteItem = (id: number) => request.delete(`/coding/items/${id}`)
