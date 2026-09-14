<template>
  <el-container class="layout" direction="vertical">
    <!-- 顶部导航栏：左段与侧栏连通（同宽同底色），菜单从侧栏右侧开始 -->
    <header class="topbar">
      <div class="brand-zone">
        <span class="logo-mark">秋</span>
        <span class="logo-name">个人 App</span>
      </div>
      <div class="topbar-main">
        <el-menu mode="horizontal" router :default-active="activePath" class="top-menu">
          <el-menu-item v-for="item in topItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
        <!-- 战役徽章（从第一笔投递算起） -->
        <div class="campaign num">
          <template v-if="campaignDays !== null">
            第 <span class="accent">{{ campaignDays }}</span> 天
            <span class="sep">·</span>
            {{ store.applications.length }} 投递
          </template>
          <template v-else>开始记录你的秋招</template>
        </div>
      </div>
    </header>

    <el-container class="body">
      <!-- 侧边栏：模块分组索引（数据源 = 模块注册表） -->
      <aside class="sidebar">
        <div v-for="g in groups" :key="g.key" class="group">
          <div class="group-title">
            <span>{{ g.label }}</span>
            <el-icon
              v-if="g.creatable && g.onCreate"
              class="add-btn"
              title="新增分类"
              @click="g.onCreate?.()"
            >
              <Plus />
            </el-icon>
          </div>
          <router-link
            v-for="item in g.items"
            :key="item.path"
            :to="item.path"
            class="group-item"
            :class="{ active: activePath === item.path }"
          >
            <span class="group-item-label">{{ item.title }}</span>
            <span v-if="item.actions?.length" class="item-actions" @click.stop.prevent>
              <el-icon
                v-for="a in item.actions"
                :key="a.title"
                :title="a.title"
                class="action-icon"
                @click="a.handler()"
              >
                <component :is="a.icon" />
              </el-icon>
            </span>
          </router-link>
          <div v-if="g.items.length === 0" class="group-empty">筹备中，敬请期待</div>
        </div>
        <div class="sidebar-foot">
          <router-link
            to="/settings"
            class="foot-settings"
            :class="{ active: route.path === '/settings' }"
          >
            <el-icon><Setting /></el-icon>
            <span>设置</span>
          </router-link>
          <span>秋招加油 💪</span>
        </div>
      </aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import { modules } from '@/modules'
// 注：战役徽章与 qa 分类菜单读取各自模块 store；模块化演进时再抽离
import { useJobsStore } from '@/modules/jobs/store'
import { useQaStore } from '@/modules/qa/store'

const route = useRoute()
const store = useJobsStore()
const qaStore = useQaStore()

onMounted(() => {
  void store.ensureLoaded() // 战役徽章数据
  void qaStore.ensureLoaded() // qa 分类菜单
})

/** 侧栏分组 = 模块 → { 显示名, 菜单项 }；模块提供 menu() 时用动态菜单（如 qa 分类）；sidebar: false 的模块不生成分组 */
const groups = computed(() =>
  modules
    .filter((m) => m.sidebar !== false)
    .map((m) => ({
    key: m.name,
    label: m.label ?? m.name,
    creatable: !!m.creatable,
    onCreate: m.onCreate,
    items: m.menu
      ? m.menu()
      : m.routes
          .filter((r) => r.meta?.title && !r.meta?.hidden)
          .map((r) => ({ path: r.path as string, title: r.meta?.title as string })),
  })),
)

/** 顶部导航 = 侧栏全部菜单项（横向） */
const topItems = computed(() =>
  groups.value.flatMap((g) => g.items).map(({ path, title, icon }) => ({ path, title, icon })),
)

/**
 * 当前路由映射到菜单高亮项：
 * hidden 路由由 meta.activeMenu 指定归属；详情类路由（如 /qa/cat/5/12）匹配为其前缀的菜单项
 */
const activePath = computed(() => {
  const meta = route.meta as { activeMenu?: string }
  if (meta.activeMenu) return meta.activeMenu
  const hit = topItems.value.find(
    (t) => route.path === t.path || route.path.startsWith(t.path + '/'),
  )
  return hit?.path ?? route.path
})

/** 战役天数 = 从最早一笔投递日期到今天 */
const campaignDays = computed(() => {
  const dates = store.applications
    .map((a) => a.applyDate)
    .filter((d): d is string => !!d)
    .sort()
  if (!dates.length) return null
  return dayjs().diff(dayjs(dates[0]), 'day') + 1
})
</script>

<style scoped>
.layout {
  height: 100%;
}

/* ---------- 顶部导航栏 ---------- */
.topbar {
  height: 56px;
  display: flex;
  align-items: stretch;
  background: #fff;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

/* 左上角品牌区：与侧栏同宽同底色，视觉上连通成 L 型 */
.brand-zone {
  width: 216px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  background: #fafafb;
  border-right: 1px solid var(--line);
}

.logo-mark {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: grid;
  place-items: center;
}

.logo-name {
  font-size: 15px;
  font-weight: 650;
  letter-spacing: 0.01em;
  color: var(--ink);
}

.topbar-main {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 0 20px 0 8px;
}

.top-menu {
  border-bottom: none;
  --el-menu-active-color: var(--el-color-primary);
  --el-menu-hover-bg-color: #f4f5f7;
}

.top-menu :deep(.el-menu-item) {
  height: 56px;
  line-height: 56px;
  margin: 0 2px;
}

.campaign {
  margin-left: auto;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  white-space: nowrap;
}

.campaign .accent {
  color: var(--accent);
  font-size: 15px;
}

.campaign .sep {
  margin: 0 7px;
  color: var(--accent);
}

/* ---------- 侧边栏：分组索引 ---------- */
.body {
  min-height: 0;
}

.sidebar {
  width: 216px;
  flex-shrink: 0;
  background: #fafafb;
  border-right: 1px solid var(--line);
  padding: 18px 12px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.group {
  margin-bottom: 24px;
}

.group-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--ink-3);
  padding: 0 10px;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.add-btn {
  font-size: 14px;
  color: var(--ink-3);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition:
    color 0.15s ease,
    background-color 0.15s ease;
}

.add-btn:hover {
  color: var(--accent);
  background: #f1f2f4;
}

.group-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--ink-2);
  font-size: 13.5px;
  text-decoration: none;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.group-item:hover {
  background: #f1f2f4;
  color: var(--ink);
}

.group-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
  box-shadow: inset 3px 0 0 var(--accent);
}

.group-item-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* hover 显示分类的重命名 / 删除小按钮 */
.item-actions {
  display: none;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.group-item:hover .item-actions {
  display: inline-flex;
}

.action-icon {
  font-size: 13px;
  color: var(--ink-3);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
}

.action-icon:hover {
  color: var(--ink);
  background: #e8eaed;
}

.group-empty {
  padding: 6px 10px;
  font-size: 12px;
  color: var(--ink-3);
}

.sidebar-foot {
  margin-top: auto;
  padding: 0 10px;
  font-size: 12px;
  color: var(--ink-3);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.foot-settings {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 8px;
  margin-left: -8px;
  border-radius: 8px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-2);
  text-decoration: none;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.foot-settings:hover {
  background: #f1f2f4;
  color: var(--ink);
}

.foot-settings.active {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

/* ---------- 主区 ---------- */
.main {
  padding: 24px 28px;
  overflow-y: auto;
}
</style>