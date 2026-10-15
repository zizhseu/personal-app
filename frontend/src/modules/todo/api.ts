import request from '@/shared/api/request'
import type { TodoCategory, TodoItem, TodoPayload, TodoUpdate } from './types'

export const fetchCategories = () => request.get<unknown, TodoCategory[]>('/todo/categories')
export const createCategory = (name: string) => request.post<unknown, TodoCategory>('/todo/categories', { name })
export const renameCategory = (id: number, name: string) => request.put<unknown, TodoCategory>(`/todo/categories/${id}`, { name })
export const deleteCategory = (id: number) => request.delete(`/todo/categories/${id}`)
export const fetchItems = () => request.get<unknown, TodoItem[]>('/todo/items')
export const createItem = (payload: TodoPayload) => request.post<unknown, TodoItem>('/todo/items', payload)
export const updateItem = (id: number, payload: TodoUpdate) => request.put<unknown, TodoItem>(`/todo/items/${id}`, payload)
export const deleteItem = (id: number) => request.delete(`/todo/items/${id}`)
