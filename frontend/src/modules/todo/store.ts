import { ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import * as api from './api'
import type { TodoCategory, TodoItem, TodoPayload, TodoUpdate } from './types'

export type { TodoCategory } from './types'

/** 目录与事项统一加载；并发挂载共享请求，避免旧响应覆盖刚保存的数据。 */
export const useTodoStore = defineStore('todo', () => {
  const categories = ref<TodoCategory[]>([])
  const items = ref<TodoItem[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const failed = ref(false)
  let loadPromise: Promise<void> | null = null

  function loadAll(): Promise<void> {
    if (loadPromise) return loadPromise
    loading.value = true
    failed.value = false
    loadPromise = (async () => {
      try {
        const [nextCategories, nextItems] = await Promise.all([api.fetchCategories(), api.fetchItems()])
        categories.value = nextCategories
        items.value = nextItems
        loaded.value = true
      } catch {
        failed.value = true
      } finally {
        loading.value = false
        loadPromise = null
      }
    })()
    return loadPromise
  }

  async function ensureLoaded() {
    if (loadPromise) await loadPromise
    else if (!loaded.value) await loadAll()
  }

  async function addCategory(name: string) {
    await ensureLoaded()
    const category = await api.createCategory(name)
    categories.value.push(category)
    ElMessage.success('已创建目录')
    return category
  }

  async function renameCategory(id: number, name: string) {
    await ensureLoaded()
    const category = await api.renameCategory(id, name)
    categories.value = categories.value.map((item) => item.id === id ? category : item)
    ElMessage.success('已重命名')
  }

  async function removeCategory(id: number) {
    await ensureLoaded()
    await api.deleteCategory(id)
    categories.value = categories.value.filter((item) => item.id !== id)
    ElMessage.success('已删除目录')
  }

  async function create(payload: TodoPayload) {
    await ensureLoaded()
    const item = await api.createItem(payload)
    items.value.unshift(item)
    ElMessage.success('已添加待办')
    return item
  }

  async function update(id: number, payload: TodoUpdate, silent = false) {
    await ensureLoaded()
    const item = await api.updateItem(id, payload)
    items.value = items.value.map((row) => row.id === id ? item : row)
    if (!silent) ElMessage.success('已保存待办')
    return item
  }

  /** 批量删除（列表多选）：逐条请求，成功一次提示 */
  async function removeMany(ids: number[]) {
    await ensureLoaded()
    for (const id of ids) await api.deleteItem(id)
    const idSet = new Set(ids)
    items.value = items.value.filter((item) => !idSet.has(item.id))
    ElMessage.success(`已删除 ${ids.length} 条待办`)
  }

  return { categories, items, loaded, loading, failed, loadAll, ensureLoaded, addCategory, renameCategory, removeCategory, create, update, removeMany }
})
