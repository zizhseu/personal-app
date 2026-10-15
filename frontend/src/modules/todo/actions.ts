import { ElMessageBox } from 'element-plus'
import router from '@/router'
import { useTodoStore, type TodoCategory } from './store'

async function promptName(title: string, initial = ''): Promise<string | null> {
  try {
    const { value } = await ElMessageBox.prompt('目录名称', title, {
      inputValue: initial,
      inputValidator: (value) => {
        if (!value?.trim()) return '名称不能为空'
        return value.trim().length <= 50 || '名称不能超过 50 个字符'
      },
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    return value.trim()
  } catch {
    return null
  }
}

export async function createCategory() {
  const name = await promptName('新建待办目录')
  if (!name) return
  try {
    const category = await useTodoStore().addCategory(name)
    await router.push(`/todo/cat/${category.id}`)
  } catch { /* 请求拦截器已显示错误。 */ }
}

export async function renameCategory(category: TodoCategory) {
  const name = await promptName('重命名目录', category.name)
  if (!name || name === category.name) return
  try {
    await useTodoStore().renameCategory(category.id, name)
  } catch { /* 请求拦截器已显示错误。 */ }
}

export async function removeCategory(category: TodoCategory) {
  const confirmed = await ElMessageBox.confirm(`确定删除目录「${category.name}」吗？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!confirmed) return
  try {
    const store = useTodoStore()
    await store.removeCategory(category.id)
    if (router.currentRoute.value.path === `/todo/cat/${category.id}`) {
      await router.replace(store.categories[0] ? `/todo/cat/${store.categories[0].id}` : '/todo')
    }
  } catch { /* 请求拦截器已显示错误。 */ }
}
