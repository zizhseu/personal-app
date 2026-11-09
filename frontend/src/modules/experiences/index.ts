import { Collection } from '@element-plus/icons-vue'
import type { AppModule } from '@/shared/types/module'

export const experiencesModule: AppModule = {
  name: 'experiences', label: '面经搜集',
  routes: [{ path: '/experiences', name: 'experiences', component: () => import('./views/ExperiencesView.vue'), meta: { title: '面经搜集', icon: Collection } }],
}
