<template>
  <el-card shadow="never" class="section">
    <template #header>
      <div class="card-header">
        <span class="sec-title">
          {{ title }}
          <span class="count num" :class="{ 'count-danger': danger }">{{ items.length }}</span>
        </span>
      </div>
    </template>

    <template v-if="items.length > 0">
      <div class="list">
        <div
          v-for="item in paged"
          :key="item.key"
          class="item-card"
          :class="[{ expired: danger }, urgencyClass(item)]"
          @click="emit('open', item)"
        >
          <span class="time num" :class="{ 'time-danger': danger }">{{ item.time }}</span>
          <el-tag effect="plain" size="small" :type="item.kind === 'event' ? 'warning' : ''">
            {{ item.typeLabel }}
          </el-tag>
          <span class="title">{{ item.title }}</span>
          <span v-if="relAppName(item)" class="rel">（{{ relAppName(item) }}）</span>
          <span v-if="item.location" class="location">
            <el-icon><Location /></el-icon>{{ item.location }}
          </span>
          <span class="spacer" />
          <!-- 自定义日程：直接编辑 / 删除 -->
          <template v-if="item.kind === 'event'">
            <el-button link type="primary" size="small" @click.stop="emit('editEvent', item.event!)">
              编辑
            </el-button>
            <el-button link type="danger" size="small" @click.stop="emit('removeEvent', item.event!)">
              删除
            </el-button>
          </template>
          <el-icon v-else class="arrow"><ArrowRight /></el-icon>
        </div>
      </div>
      <div v-if="items.length > PAGE_SIZE" class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="PAGE_SIZE"
          :total="items.length"
          :pager-count="5"
          small
          background
          layout="prev, pager, next"
        />
      </div>
    </template>
    <el-empty v-else :description="emptyText" :image-size="70" />
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'
import type { ScheduleEvent, ScheduleItem } from '../types'
import { useJobsStore } from '../store'

const props = defineProps<{
  title: string
  emptyText: string
  items: ScheduleItem[]
  /** 过期容器：警示样式 */
  danger?: boolean
  /** 待办容器：按截止紧急度变色（红/黄/绿） */
  colored?: boolean
}>()

const emit = defineEmits<{
  open: [item: ScheduleItem]
  editEvent: [event: ScheduleEvent]
  removeEvent: [event: ScheduleEvent]
}>()

const store = useJobsStore()

const PAGE_SIZE = 5
const page = ref(1)

const paged = computed(() =>
  props.items.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE),
)

/** 待办紧急度：<24h 红 / <48h 黄 / 其他绿 */
function urgencyClass(item: ScheduleItem): string {
  if (!props.colored) return ''
  const hours = dayjs(item.scheduledAt).diff(dayjs(), 'hour', true)
  if (hours <= 24) return 'urgent'
  if (hours <= 48) return 'soon'
  return 'safe'
}

// 数据变化后页码夹紧
watch(
  () => props.items.length,
  (len) => {
    const maxPage = Math.max(1, Math.ceil(len / PAGE_SIZE))
    if (page.value > maxPage) page.value = maxPage
  },
)

/** 自定义日程关联投递的显示名（灰字提示） */
function relAppName(item: ScheduleItem): string | null {
  if (item.kind !== 'event' || !item.applicationId) return null
  const app = store.applications.find((a) => a.id === item.applicationId)
  if (!app) return null
  return app.position ? `${app.company} · ${app.position}` : app.company
}
</script>

<style scoped>
.section {
  border-radius: var(--radius-card);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sec-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.count {
  font-size: 12px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--el-color-primary-light-9);
  color: var(--ink-2);
}

.count-danger {
  background: #fef2f2;
  color: #dc2626;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.item-card:hover {
  background: #f6f7f8;
}

.item-card.expired {
  background: #fef7f6;
}

.item-card.expired:hover {
  background: #fdeeea;
}

/* 待办紧急度：一天内红、两天内黄、大于两天绿 */
.item-card.urgent {
  background: #fef2f2;
  border-left: 3px solid #dc2626;
}

.item-card.soon {
  background: #fffbeb;
  border-left: 3px solid #d97706;
}

.item-card.safe {
  background: #f0fdf4;
  border-left: 3px solid #16a34a;
}

.item-card.urgent:hover {
  background: #fde8e8;
}

.item-card.soon:hover {
  background: #fdf3d8;
}

.item-card.safe:hover {
  background: #dcfce7;
}

.time {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.time-danger {
  color: #dc2626;
}

.title {
  color: #374151;
}

.rel {
  color: var(--ink-3);
  font-size: 12px;
}

.location {
  color: var(--ink-2);
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.spacer {
  flex: 1;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 10px;
}
</style>