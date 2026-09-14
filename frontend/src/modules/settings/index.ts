import type { RouteRecordRaw } from 'vue-router'
import type { AppModule } from '@/shared/types/module'

/** settings 模块：全局应用偏好。入口固定在侧栏左下角，不生成分组菜单 */
export const settingsModule: AppModule = {
  name: 'settings',
  label: '设置',
  sidebar: false,
  routes: [
    {
      path: '/settings',
      name: 'settings',
      component: () => import('./views/SettingsView.vue'),
      meta: { hidden: true },
    },
  ] as RouteRecordRaw[],
}