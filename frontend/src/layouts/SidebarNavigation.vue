<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-mark" aria-hidden="true">秋</span>
      <div>
        <div class="brand-name">个人 App</div>
        <div class="brand-caption">秋招与学习</div>
      </div>
    </div>

    <nav class="navigation" aria-label="功能导航">
      <section v-for="group in groups" :key="group.key" class="nav-group" :aria-label="group.label">
        <div class="group-heading">
          <span>{{ group.label }}</span>
          <button
            v-if="group.creatable && group.onCreate"
            type="button"
            class="icon-button"
            :aria-label="`新增${group.label}分类`"
            title="新增分类"
            @click="group.onCreate?.()"
          >
            <el-icon><Plus /></el-icon>
          </button>
        </div>
        <div
          v-for="item in group.items"
          :key="item.path"
          class="nav-row"
          :class="{ active: activePath === item.path }"
        >
          <router-link
            :to="item.path"
            class="nav-link"
            :aria-current="activePath === item.path ? 'page' : undefined"
            :title="item.title"
            @click="$emit('navigate')"
          >
            <el-icon class="nav-icon"><component :is="item.icon ?? FolderOpened" /></el-icon>
            <span class="nav-label">{{ item.title }}</span>
          </router-link>
          <div v-if="item.actions?.length" class="item-actions">
            <button
              v-for="action in item.actions"
              :key="action.title"
              type="button"
              class="icon-button"
              :aria-label="`${action.title}${item.title}`"
              :title="action.title"
              @click="action.handler()"
            >
              <el-icon><component :is="action.icon" /></el-icon>
            </button>
          </div>
        </div>
        <p v-if="!group.items.length" class="group-empty">
          {{ group.creatable ? '点击 + 新建分类' : '筹备中，敬请期待' }}
        </p>
      </section>
    </nav>

    <div class="sidebar-footer">
      <router-link to="/settings" class="settings-link" @click="$emit('navigate')">
        <el-icon><Setting /></el-icon>
        <span>设置</span>
      </router-link>
      <span class="footer-caption">秋招加油</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { FolderOpened } from '@element-plus/icons-vue'
import type { MenuItem } from '@/shared/types/module'

defineProps<{
  groups: {
    key: string
    label: string
    creatable: boolean
    onCreate?: () => void
    items: MenuItem[]
  }[]
  activePath: string
}>()

defineEmits<{ navigate: [] }>()
</script>

<style scoped>
.sidebar {
  width: 232px;
  height: 100%;
  min-height: 0;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--card);
  border-right: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 10px; padding: 24px 22px 22px; flex-shrink: 0; }
.brand-mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 11px;
  background: var(--brand-gradient);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 4px 12px rgb(99 102 241 / 18%);
}
.brand-name { color: var(--ink); font-size: 16px; font-weight: 700; }
.brand-caption { margin-top: 3px; color: var(--ink-3); font-size: 11px; }
.navigation { flex: 1; min-height: 0; overflow-y: auto; padding: 0 12px 16px; }
.nav-group + .nav-group { margin-top: 20px; }
.group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 28px;
  padding: 0 10px;
  margin-bottom: 4px;
  color: var(--ink-3);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.04em;
}
.nav-row {
  display: flex;
  align-items: center;
  min-height: 40px;
  margin-top: 2px;
  border: 1px solid transparent;
  border-radius: 9px;
  color: var(--ink-2);
  transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
}
.nav-row:hover { color: var(--ink); background: var(--surface-hover); }
.nav-row.active {
  color: var(--el-color-primary);
  font-weight: 600;
  background: var(--surface-selected);
  border-color: var(--line);
  box-shadow: var(--shadow-sm);
}
.nav-link {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  min-height: 40px;
  gap: 10px;
  padding: 8px 10px;
  color: inherit;
  border-radius: 8px;
  text-decoration: none;
  font-size: 13px;
}
.nav-icon { flex-shrink: 0; font-size: 16px; }
.nav-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-actions { display: flex; padding-right: 4px; opacity: 0; }
.nav-row:hover .item-actions, .nav-row:focus-within .item-actions { opacity: 1; }
.icon-button {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  padding: 0;
  color: var(--ink-3);
  border: 0;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
}
.icon-button:hover { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.group-empty { margin: 0; padding: 6px 10px; color: var(--ink-3); font-size: 12px; line-height: 1.6; }
.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  margin: 0 12px;
  padding: 14px 0;
  border-top: 1px solid var(--line);
}
.settings-link {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 8px 10px;
  color: var(--ink-2);
  border-radius: 8px;
  font-size: 13px;
  text-decoration: none;
}
.settings-link:hover { background: var(--surface-hover); }
.settings-link.router-link-active { color: var(--el-color-primary); background: var(--surface-selected); }
.footer-caption { padding-right: 8px; color: var(--ink-3); font-size: 11px; }
@media (hover: none) {
  .item-actions { opacity: 1; }
  .icon-button { width: 30px; height: 32px; }
}
@media (max-width: 1100px) and (min-width: 761px) {
  .sidebar { width: 216px; }
  .brand { padding-inline: 20px; }
}
</style>
