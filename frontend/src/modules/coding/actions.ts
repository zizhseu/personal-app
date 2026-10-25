import { ElMessageBox } from 'element-plus'
import router from '@/router'
import { useCodingStore } from './store'
import type { CodingCategory } from './types'

async function promptName(title: string, initial = '') {
  try {
    const { value } = await ElMessageBox.prompt('分类名称', title, {
      inputValue: initial, confirmButtonText: '确定', cancelButtonText: '取消',
      inputValidator: value => !!value?.trim() && value.trim().length <= 50 || '请输入 1–50 个字符的分类名称',
    })
    return value.trim()
  } catch { return null }
}
export async function createCategory() {
  const name = await promptName('新增手撕题分类')
  if (!name) return
  try { const category = await useCodingStore().addCategory(name); await router.push(`/coding/cat/${category.id}`) } catch { /* 拦截器显示错误。 */ }
}
export async function renameCategory(category: CodingCategory) {
  const name = await promptName('重命名手撕题分类', category.name)
  if (!name || name === category.name) return
  try { await useCodingStore().renameCategory(category.id, name) } catch { /* 拦截器显示错误。 */ }
}
export async function removeCategory(category: CodingCategory) {
  const confirmed = await ElMessageBox.confirm(`删除分类「${category.name}」？有题目的分类需要先移动或删除题目。`, '删除分类', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!confirmed) return
  try {
    await useCodingStore().removeCategory(category.id)
    if (Number(router.currentRoute.value.params.id) === category.id && router.currentRoute.value.path.startsWith('/coding/')) await router.replace('/coding')
  } catch { /* 拦截器显示错误。 */ }
}
