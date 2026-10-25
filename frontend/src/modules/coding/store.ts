import { ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import * as api from './api'
import type { CodingCategory, CodingPayload, CodingStatus, CodingSummary } from './types'

export const useCodingStore = defineStore('coding', () => {
  const categories = ref<CodingCategory[]>([]), items = ref<CodingSummary[]>([])
  const loaded = ref(false), loading = ref(false), failed = ref(false)
  let pending: Promise<void> | null = null

  function loadAll(): Promise<void> {
    if (pending) return pending
    loading.value = true
    failed.value = false
    pending = (async () => {
      try {
        const [nextCategories, nextItems] = await Promise.all([api.fetchCategories(), api.fetchItems()])
        categories.value = nextCategories
        items.value = nextItems
        loaded.value = true
      } catch { failed.value = true } finally { loading.value = false; pending = null }
    })()
    return pending
  }
  async function ensureLoaded() { if (pending) await pending; else if (!loaded.value) await loadAll() }
  async function addCategory(name: string) {
    await ensureLoaded()
    const category = await api.createCategory(name)
    categories.value.push(category)
    ElMessage.success('已创建手撕题分类')
    return category
  }
  async function renameCategory(id: number, name: string) {
    await ensureLoaded()
    const category = await api.renameCategory(id, name)
    categories.value = categories.value.map(row => row.id === id ? category : row)
    ElMessage.success('分类已重命名')
  }
  async function removeCategory(id: number) {
    await ensureLoaded()
    await api.deleteCategory(id)
    categories.value = categories.value.filter(row => row.id !== id)
    ElMessage.success('分类已删除')
  }
  async function save(data: CodingPayload, id?: number, silent = false) {
    await ensureLoaded()
    const item = await api.saveItem(data, id, silent)
    items.value = [item, ...items.value.filter(row => row.id !== item.id)]
    if (!silent) ElMessage.success('手撕题已保存')
    return item
  }
  async function setStatus(id: number, status: CodingStatus) {
    const item = await api.patchStatus(id, status)
    items.value = items.value.map(row => row.id === id ? item : row)
    return item
  }
  async function remove(id: number) {
    await api.deleteItem(id)
    items.value = items.value.filter(row => row.id !== id)
    ElMessage.success('手撕题已删除')
  }
  return { categories, items, loaded, loading, failed, loadAll, ensureLoaded, addCategory, renameCategory, removeCategory, save, setStatus, remove }
})
