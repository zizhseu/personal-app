<template>
  <el-container class="layout" direction="horizontal">
    <SidebarNavigation class="desktop-sidebar" :groups="groups" :active-path="activePath" :collapsed-groups="collapsedGroups" @toggle-group="toggleGroup" />
    <el-container class="workspace" direction="vertical">
      <header class="topbar">
        <div class="page-location">
          <button type="button" class="menu-toggle" aria-label="打开功能导航" @click="navigationOpen = true">
            <el-icon><Expand /></el-icon>
          </button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ activeGroup?.label ?? '个人偏好' }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ activeItem?.title ?? activeGroup?.label ?? '设置' }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-meta">
          <span class="today">{{ today }}</span>
          <div class="campaign num">
            <template v-if="campaignDays !== null">
              第 <span class="campaign-number">{{ campaignDays }}</span> 天
              <span class="campaign-separator" aria-hidden="true">·</span>
              {{ store.applications.length }} 投递
            </template>
            <template v-else>开始记录你的秋招</template>
          </div>
        </div>
      </header>
      <el-main class="main">
        <div class="content"><router-view /></div>
      </el-main>
    </el-container>
    <el-drawer v-model="navigationOpen" title="功能导航" direction="ltr" size="264px" destroy-on-close class="navigation-drawer">
      <SidebarNavigation :groups="groups" :active-path="activePath" :collapsed-groups="collapsedGroups" @toggle-group="toggleGroup" @navigate="navigationOpen = false" />
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, type Component } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import { modules } from '@/modules'
import type { MenuItem } from '@/shared/types/module'
import { useJobsStore } from '@/modules/jobs/store'
import { useQaStore } from '@/modules/qa/store'
import { useQuizStore } from '@/modules/quiz/store'
import { useTodoStore } from '@/modules/todo/store'
import { useCodingStore } from '@/modules/coding/store'
import SidebarNavigation from './SidebarNavigation.vue'

const route = useRoute()
const store = useJobsStore()
const qaStore = useQaStore()
const quizStore = useQuizStore()
const todoStore = useTodoStore()
const codingStore = useCodingStore()
const navigationOpen = ref(false)
const collapseStorageKey = 'personal-app.sidebar.collapsed-groups.v1'
const collapsedGroups = ref<string[]>(loadCollapsedGroups())
const today = dayjs().format('M月D日 dddd')

function loadCollapsedGroups(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(collapseStorageKey) ?? '[]')
    return Array.isArray(value) ? value.filter((key): key is string => typeof key === 'string') : []
  } catch {
    return []
  }
}

function toggleGroup(key: string) {
  collapsedGroups.value = collapsedGroups.value.includes(key)
    ? collapsedGroups.value.filter(value => value !== key)
    : [...collapsedGroups.value, key]
  try {
    localStorage.setItem(collapseStorageKey, JSON.stringify(collapsedGroups.value))
  } catch { /* 浏览器禁止存储时，本次打开期间仍可折叠。 */ }
}

onMounted(() => {
  void store.ensureLoaded()
  void qaStore.ensureLoaded()
  void quizStore.ensureLoaded()
  void todoStore.ensureLoaded()
  void codingStore.ensureLoaded()
})

watch(() => route.path, () => { navigationOpen.value = false })

/** 导航仍从模块注册表派生，保留所有动态分类与分类操作。 */
const groups = computed(() =>
  modules.filter((module) => module.sidebar !== false).map((module) => ({
    key: module.name,
    label: module.label ?? module.name,
    creatable: !!module.creatable,
    onCreate: module.onCreate,
    items: module.menu
      ? module.menu()
      : module.routes
          .filter((record) => record.meta?.title && !record.meta?.hidden)
          .map<MenuItem>((record) => ({
            path: record.path,
            title: record.meta?.title as string,
            icon: record.meta?.icon as Component | undefined,
          })),
  })),
)

const menuItems = computed(() => groups.value.flatMap((group) => group.items))
const activePath = computed(() => {
  const activeMenu = route.meta.activeMenu as string | undefined
  if (activeMenu) return activeMenu
  // 优先匹配最长路径，避免相邻分类或嵌套路由误高亮。
  return [...menuItems.value]
    .sort((left, right) => right.path.length - left.path.length)
    .find((item) => route.path === item.path || route.path.startsWith(item.path + '/'))?.path ?? route.path
})
const activeGroup = computed(() => {
  const matched = groups.value.find((group) => group.items.some((item) => item.path === activePath.value))
  if (matched) return matched
  const routeModule = modules.find((module) => module.routes.some((record) => record.name === route.name))
  return groups.value.find((group) => group.key === routeModule?.name)
})
const activeItem = computed(() => menuItems.value.find((item) => item.path === activePath.value))

/** 秋招天数从最早一笔投递日期算起。 */
const campaignDays = computed(() => {
  const dates = store.applications.map((application) => application.applyDate).filter((date): date is string => !!date).sort()
  if (!dates.length) return null
  return dayjs().diff(dayjs(dates[0]), 'day') + 1
})
</script>

<style scoped>
.layout { height: 100dvh; min-height: 0; overflow: hidden; }
.workspace { min-width: 0; min-height: 0; }
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  min-height: 76px;
  gap: 20px;
  padding: 16px 28px;
  background: var(--paper);
}
.page-location { display: flex; align-items: center; gap: 12px; min-width: 0; }
.page-location :deep(.el-breadcrumb) { font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.page-location :deep(.el-breadcrumb__inner) { color: var(--ink-3); }
.page-location :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) { color: var(--ink); font-weight: 600; }
.topbar-meta { display: flex; align-items: center; flex-shrink: 0; gap: 16px; }
.today { color: var(--ink-3); font-size: 12px; }
.campaign {
  padding: 7px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--card);
  color: var(--ink-2);
  font-size: 12px;
  white-space: nowrap;
}
.campaign-number { color: var(--el-color-primary); font-weight: 650; }
.campaign-separator { padding: 0 6px; color: var(--ink-3); }
.menu-toggle {
  display: none;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--card);
  color: var(--ink-2);
  font-size: 18px;
  cursor: pointer;
}
.main { min-width: 0; padding: 4px 28px 28px; overflow: auto; overscroll-behavior: contain; }
/* 内容宽度由当前窗口决定，全屏与侧栏展开时均铺满可用区域。 */
.content { width: 100%; min-width: 0; }
@media (max-width: 1000px) {
  .today { display: none; }
  .topbar { padding-inline: 20px; }
  .main { padding-inline: 20px; }
}
@media (max-width: 760px) {
  .desktop-sidebar { display: none; }
  .menu-toggle { display: inline-flex; }
  .topbar { min-height: 68px; padding: 12px 16px; gap: 12px; }
  .topbar-meta { min-width: 0; flex-shrink: 1; }
  .campaign { padding: 7px 9px; font-size: 11px; }
  .main { padding: 8px 16px 20px; }
}
@media (max-width: 420px) {
  .page-location :deep(.el-breadcrumb__item:first-child) { display: none; }
}
</style>

<style>
.navigation-drawer .el-drawer__body { padding: 0; overflow: hidden; }
.navigation-drawer .el-drawer__header { margin-bottom: 0; padding: 16px 20px; font-size: 14px; }
.navigation-drawer .sidebar { width: 100%; border-right: 0; }
</style>
