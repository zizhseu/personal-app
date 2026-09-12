import type { RouteRecordRaw } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Delete, EditPen } from '@element-plus/icons-vue'
import type { AppModule, MenuItem } from '@/shared/types/module'
import router from '@/router'
import { useQaStore } from './store'
import type { QaCategoryEntity } from './types'

/** 弹窗输入分类名称；取消返回 null */
async function promptCategoryName(title: string, initial = ''): Promise<string | null> {
  try {
    const { value } = await ElMessageBox.prompt('分类名称', title, {
      inputValue: initial,
      inputPattern: /\S/,
      inputErrorMessage: '名称不能为空',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    return value.trim() || null
  } catch {
    return null
  }
}

/** 侧栏 + 号：新增分类并跳转到新分类页 */
async function createCategoryFlow(): Promise<void> {
  const store = useQaStore()
  const name = await promptCategoryName('新增分类')
  if (!name) return
  const cat = await store.addCategory(name)
  await router.push(`/qa/cat/${cat.id}`)
}

/** 侧栏项操作：重命名 */
function renameFlow(cat: QaCategoryEntity): void {
  void (async () => {
    const name = await promptCategoryName('重命名分类', cat.name)
    if (!name) return
    await useQaStore().renameCategory(cat.id, name)
  })()
}

/** 侧栏项操作：删除（分类下有题时后端 400，由拦截器弹中文提示） */
function removeFlow(cat: QaCategoryEntity): void {
  void (async () => {
    const ok = await ElMessageBox.confirm(`确定删除分类「${cat.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    }).catch(() => false)
    if (!ok) return
    const store = useQaStore()
    await store.removeCategory(cat.id)
    // 正停在被删分类页时，退到剩余的第一个分类
    if (router.currentRoute.value.path.startsWith(`/qa/cat/${cat.id}`)) {
      const first = store.categories[0]
      if (first) await router.push(`/qa/cat/${first.id}`)
    }
  })()
}

/** 动态分类菜单（响应式：store.categories 变化自动更新） */
function categoryMenu(): MenuItem[] {
  const store = useQaStore()
  return store.categories.map((c) => ({
    path: `/qa/cat/${c.id}`,
    title: c.name,
    actions: [
      { icon: EditPen, title: '重命名', handler: () => renameFlow(c) },
      { icon: Delete, title: '删除', handler: () => removeFlow(c) },
    ],
  }))
}

/** qa 模块：面试八股（分类由用户自建，详情/新建共用 QaDetailView，页面内直接编辑） */
export const qaModule: AppModule = {
  name: 'qa',
  label: '面试八股',
  creatable: true,
  menu: categoryMenu,
  onCreate: () => createCategoryFlow(),
  routes: [
    {
      path: '/qa/cat/:id(\\d+)',
      name: 'qa-cat',
      component: () => import('./views/QaListView.vue'),
      meta: { hidden: true },
    },
    {
      path: '/qa/cat/:id(\\d+)/new',
      name: 'qa-new',
      component: () => import('./views/QaDetailView.vue'),
      meta: { hidden: true },
    },
    {
      path: '/qa/cat/:id(\\d+)/:itemId(\\d+)',
      name: 'qa-detail',
      component: () => import('./views/QaDetailView.vue'),
      meta: { hidden: true },
    },
  ] as RouteRecordRaw[],
}