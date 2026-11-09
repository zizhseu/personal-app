import type { RouteRecordRaw } from 'vue-router'
import { Microphone } from '@element-plus/icons-vue'
import type { AppModule } from '@/shared/types/module'
import { experiencesModule } from '../experiences'

/** AI 工具集通过模块路由组合各项工具。 */
export const aitoolsModule: AppModule = {
  name: 'aitools',
  label: 'AI 工具',
  routes: [
    {
      path: '/aitools/interview',
      name: 'aitools-interview',
      component: () => import('./views/InterviewView.vue'),
      meta: { title: 'AI 面试', icon: Microphone },
    },
    ...experiencesModule.routes,
  ] as RouteRecordRaw[],
}
