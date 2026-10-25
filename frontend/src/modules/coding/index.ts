import { Collection, Delete, EditPen } from '@element-plus/icons-vue'
import type { AppModule } from '@/shared/types/module'
import { useCodingStore } from './store'
import { createCategory, renameCategory, removeCategory } from './actions'

export const codingModule: AppModule = {
  name: 'coding', label: '代码手撕', creatable: true, onCreate: createCategory,
  menu: () => [{ path: '/coding', title: '全部题目', icon: Collection }, ...useCodingStore().categories.map(category => ({
    path: `/coding/cat/${category.id}`, title: category.name,
    actions: [
      { icon: EditPen, title: '重命名', handler: () => { void renameCategory(category) } },
      { icon: Delete, title: '删除', handler: () => { void removeCategory(category) } },
    ],
  }))],
  routes: [
    { path: '/coding', name: 'coding-home', component: () => import('./views/CodingList.vue'), meta: { hidden: true } },
    { path: '/coding/cat/:id(\\d+)', name: 'coding-category', component: () => import('./views/CodingList.vue'), meta: { hidden: true } },
    { path: '/coding/cat/:id(\\d+)/new', name: 'coding-new', component: () => import('./views/CodingDetail.vue'), meta: { hidden: true } },
    { path: '/coding/cat/:id(\\d+)/:itemId(\\d+)', name: 'coding-detail', component: () => import('./views/CodingDetail.vue'), meta: { hidden: true } },
  ],
}
