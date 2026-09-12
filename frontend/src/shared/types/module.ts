import type { Component } from 'vue'
import type { RouteRecordRaw } from 'vue-router'

/** 菜单项上的小操作（hover 显示，如分类的重命名/删除） */
export interface MenuAction {
  icon: Component
  title: string
  handler: () => void
}

/** 菜单项（静态路由派生或模块动态提供） */
export interface MenuItem {
  path: string
  title: string
  icon?: Component
  /** hover 显示的小操作 */
  actions?: MenuAction[]
}

/** 功能模块注册契约：新增模块实现此接口并登记进 modules/index.ts */
export interface AppModule {
  /** 模块名，如 'jobs' */
  name: string
  /** 模块显示名：作为侧边栏分组标题（如「简历投递」）；缺省用 name */
  label?: string
  /** 模块的全部路由（扁平）；meta.title 有值且 meta.hidden 不为 true 的项进入菜单 */
  routes: RouteRecordRaw[]
  /**
   * 动态菜单项（如 qa 的用户自建分类）。
   * 提供时侧边栏/顶栏使用它替代静态路由派生的菜单。
   */
  menu?: () => MenuItem[]
  /** 分组可新建条目：侧栏分组标题旁显示 + 号 */
  creatable?: boolean
  /** + 号点击回调（模块自行实现新建交互） */
  onCreate?: () => void
}