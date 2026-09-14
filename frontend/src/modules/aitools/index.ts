import type { RouteRecordRaw } from 'vue-router'
import { Microphone } from '@element-plus/icons-vue'
import type { AppModule } from '@/shared/types/module'

/** aitools 模块：AI 工具集（首个工具：AI 面试） */
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
  ] as RouteRecordRaw[],
}