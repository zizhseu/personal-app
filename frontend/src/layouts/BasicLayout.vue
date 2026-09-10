<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">📋 个人 App</div>
      <el-menu router :default-active="route.path" class="menu">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
      <div class="aside-footer">秋招加油！💪</div>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { modules } from '@/modules'

const route = useRoute()

// 菜单 = 所有模块路由中 meta.title 有值且未标记 hidden 的项（与路由单一数据源）
const menuItems = computed(() =>
  modules
    .flatMap((m) => m.routes)
    .filter((r) => r.meta?.title && !r.meta?.hidden)
    .map((r) => ({
      path: r.path as string,
      title: r.meta?.title as string,
      icon: r.meta?.icon,
    })),
)
</script>

<style scoped>
.layout {
  height: 100%;
}

.aside {
  display: flex;
  flex-direction: column;
  background-color: #001529;
}

.logo {
  height: 56px;
  line-height: 56px;
  padding-left: 20px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.menu {
  border-right: none;
  background-color: #001529;
  flex: 1;
}

.menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.65);
}

.menu :deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.menu :deep(.el-menu-item.is-active) {
  background-color: #1677ff;
  color: #fff;
}

.aside-footer {
  padding: 16px 20px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}

.main {
  padding: 20px;
  overflow-y: auto;
}
</style>