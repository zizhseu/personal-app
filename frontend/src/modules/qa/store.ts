import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import type { QaCategoryEntity, QaItem, QaPayload, QaStatus } from './types'
import * as api from './api'

/** 面试八股数据（分类 + 题目）+ 增删改后统一刷新 */
export const useQaStore = defineStore('qa', {
  state: () => ({
    categories: [] as QaCategoryEntity[],
    items: [] as QaItem[],
    loaded: false,
    loading: false,
  }),
  actions: {
    async loadAll() {
      this.loading = true
      try {
        const [categories, items] = await Promise.all([api.fetchCategories(), api.fetchItems()])
        this.categories = categories
        this.items = items
        this.loaded = true
      } finally {
        this.loading = false
      }
    },
    async ensureLoaded() {
      if (!this.loaded) await this.loadAll()
    },
    // ---------- 分类 ----------
    async addCategory(name: string): Promise<QaCategoryEntity> {
      const cat = await api.createCategory(name)
      ElMessage.success(`已创建分类「${cat.name}」`)
      await this.loadAll()
      return cat
    },
    async renameCategory(id: number, name: string) {
      await api.renameCategory(id, name)
      ElMessage.success('已重命名')
      await this.loadAll()
    },
    async removeCategory(id: number) {
      await api.deleteCategory(id)
      ElMessage.success('已删除分类')
      await this.loadAll()
    },
    // ---------- 题目 ----------
    async create(payload: QaPayload): Promise<QaItem> {
      const item = await api.createItem(payload)
      ElMessage.success('已添加题目')
      await this.loadAll()
      return item
    },
    /** silent = 不弹成功提示（索引页快捷编辑用） */
    async update(id: number, payload: Partial<QaPayload>, silent = false) {
      await api.updateItem(id, payload)
      if (!silent) ElMessage.success('保存成功')
      await this.loadAll()
    },
    /** 切换掌握状态：静默（标签变化即反馈，复习时高频操作不打扰） */
    async patchStatus(id: number, status: QaStatus) {
      await api.patchStatus(id, status)
      await this.loadAll()
    },
    /** 标记已阅读：静默 */
    async markRead(id: number) {
      await api.markRead(id)
      await this.loadAll()
    },
    async remove(id: number) {
      await api.deleteItem(id)
      ElMessage.success('已删除')
      await this.loadAll()
    },
  },
})