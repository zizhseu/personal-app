import { createRouter, createWebHistory } from 'vue-router'
import BasicLayout from '@/layouts/BasicLayout.vue'
import { modules } from '@/modules'

// 所有模块的扁平路由，挂在布局壳下
const moduleRoutes = modules.flatMap((m) => m.routes)
// 首页重定向到第一个有菜单标题的路由
const firstPath = moduleRoutes.find((r) => r.meta?.title)?.path ?? '/'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: BasicLayout,
      redirect: firstPath,
      children: moduleRoutes,
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router