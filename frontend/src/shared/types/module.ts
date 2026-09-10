import type { RouteRecordRaw } from 'vue-router'

/** 功能模块注册契约：新增模块实现此接口并登记进 modules/index.ts */
export interface AppModule {
  /** 模块名，如 'jobs' */
  name: string
  /** 模块的全部路由（扁平）；meta.title 有值且 meta.hidden 不为 true 的项进入侧边菜单 */
  routes: RouteRecordRaw[]
}