import type { RouteRecordRaw } from 'vue-router'
import { Odometer, Tickets, Calendar } from '@element-plus/icons-vue'
import type { AppModule } from '@/shared/types/module'

/** jobs 模块声明：路由 + 菜单元信息（title 有值且非 hidden 的进菜单） */
export const jobsModule: AppModule = {
  name: 'jobs',
  label: '简历投递',
  routes: [
    { path: '/jobs', redirect: '/jobs/dashboard' },
    {
      path: '/jobs/dashboard',
      name: 'jobs-dashboard',
      component: () => import('./views/DashboardView.vue'),
      meta: { title: '看板', icon: Odometer },
    },
    {
      path: '/jobs/list',
      name: 'jobs-list',
      component: () => import('./views/ApplicationListView.vue'),
      meta: { title: '投递列表', icon: Tickets },
    },
    {
      path: '/jobs/applications/:id',
      name: 'jobs-detail',
      component: () => import('./views/ApplicationDetailView.vue'),
      meta: { hidden: true, activeMenu: '/jobs/list' },
    },
    {
      path: '/jobs/schedule',
      name: 'jobs-schedule',
      component: () => import('./views/ScheduleView.vue'),
      meta: { title: '日程', icon: Calendar },
    },
  ] as RouteRecordRaw[],
}