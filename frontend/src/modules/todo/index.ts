import { Delete, EditPen } from '@element-plus/icons-vue'
import type { AppModule } from '@/shared/types/module'
import { useTodoStore } from './store'
import { createCategory, renameCategory, removeCategory } from './actions'

export const todoModule: AppModule = {
  name: 'todo',
  label: '待办事项',
  creatable: true,
  onCreate: createCategory,
  menu: () => useTodoStore().categories.map((category) => ({
    path: `/todo/cat/${category.id}`,
    title: category.name,
    actions: [
      { icon: EditPen, title: '重命名', handler: () => { void renameCategory(category) } },
      { icon: Delete, title: '删除', handler: () => { void removeCategory(category) } },
    ],
  })),
  routes: [
    { path: '/todo', name: 'todo-home', component: () => import('./views/TodoView.vue'), meta: { hidden: true } },
    { path: '/todo/cat/:id(\\d+)', name: 'todo-category', component: () => import('./views/TodoView.vue'), meta: { hidden: true } },
  ],
}
