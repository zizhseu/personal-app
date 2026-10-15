import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import type { ParsedQuiz, QuizCategory, QuizItem, QuizPayload } from './types'
import * as api from './api'

/** 笔试选择数据（分类 + 题目）+ 增删改后统一刷新 */
export const useQuizStore = defineStore('quiz', {
  state: () => ({
    categories: [] as QuizCategory[],
    items: [] as QuizItem[],
    loaded: false,
    loading: false,
    /** 列表页码记忆：从详情返回列表时回到离开时的页 */
    listPage: 1,
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
    async addCategory(name: string): Promise<QuizCategory> {
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
    async create(payload: QuizPayload): Promise<QuizItem> {
      const item = await api.createItem(payload)
      ElMessage.success('已添加题目')
      await this.loadAll()
      return item
    },
    /** silent = 不弹成功提示（页内快捷编辑用） */
    async update(id: number, payload: Partial<QuizPayload>, silent = false) {
      await api.updateItem(id, payload)
      if (!silent) ElMessage.success('保存成功')
      await this.loadAll()
    },
    async remove(id: number) {
      await api.deleteItem(id)
      ElMessage.success('已删除')
      await this.loadAll()
    },
    /** 批量导入 AI 解析出的候选题目 */
    async importParsed(categoryId: number, parsed: ParsedQuiz[]) {
      for (const q of parsed) {
        await api.createItem({
          categoryId,
          question: q.question,
          options: q.options,
          answer: q.answer,
          qtype: q.qtype,
          analysis: q.analysis || null,
        })
      }
      ElMessage.success(`已导入 ${parsed.length} 道题目`)
      await this.loadAll()
    },
  },
})