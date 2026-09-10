<template>
  <div class="page">
    <!-- 即将到来的安排（面试轮次 + 自定义日程） -->
    <el-card shadow="never" class="section">
      <template #header>
        <div class="card-header">
          <span>接下来的安排</span>
          <div class="header-right">
            <span class="hint">轮次点击查看详情，日程卡片点击可编辑</span>
            <el-button type="primary" icon="Plus" @click="openCreateEvent">新增日程</el-button>
          </div>
        </div>
      </template>

      <template v-if="upcomingGroups.length > 0">
        <div v-for="group in upcomingGroups" :key="group.date" class="date-group">
          <div class="date-title" :class="{ today: group.isToday }">
            {{ group.date }}
            <el-tag v-if="group.isToday" type="danger" size="small" effect="plain">今天</el-tag>
            <el-tag v-else-if="group.isTomorrow" type="warning" size="small" effect="plain">
              明天
            </el-tag>
          </div>
          <div class="cards">
            <el-card
              v-for="item in group.items"
              :key="item.key"
              shadow="hover"
              class="schedule-card"
              @click="openItem(item)"
            >
              <div class="item-row">
                <span class="time">{{ item.time }}</span>
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
                  <el-button link type="primary" size="small" @click.stop="openEditEvent(item.event!)">
                    编辑
                  </el-button>
                  <el-button link type="danger" size="small" @click.stop="confirmRemoveEvent(item.event!)">
                    删除
                  </el-button>
                </template>
                <el-icon v-else class="arrow"><ArrowRight /></el-icon>
              </div>
            </el-card>
          </div>
        </div>
      </template>
      <el-empty
        v-else
        description="近期没有安排，点击右上角「新增日程」记录宣讲会等日程"
        :image-size="90"
      />
    </el-card>

    <!-- 已过期待定：提醒补录结果（仅面试轮次有结果概念） -->
    <el-card v-if="pendingPastGroups.length > 0" shadow="never" class="section">
      <template #header>
        <div class="card-header">
          <span>已过期待定</span>
          <span class="hint">这些轮次时间已过还没录结果，点击去补录</span>
        </div>
      </template>
      <div v-for="group in pendingPastGroups" :key="group.date" class="date-group">
        <div class="date-title past">{{ group.date }}</div>
        <div class="cards">
          <el-card
            v-for="item in group.items"
            :key="item.key"
            shadow="hover"
            class="schedule-card past"
            @click="openItem(item)"
          >
            <div class="item-row">
              <span class="time">{{ item.time }}</span>
              <el-tag effect="plain" size="small" type="info">{{ item.typeLabel }}</el-tag>
              <span class="title">{{ item.title }}</span>
              <span class="spacer" />
              <el-icon class="arrow"><ArrowRight /></el-icon>
            </div>
          </el-card>
        </div>
      </div>
    </el-card>

    <EventFormDialog v-model="eventVisible" :event="editingEvent" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { ROUND_TYPE_LABELS, EVENT_TYPE_LABELS } from '../constants'
import EventFormDialog from '../components/EventFormDialog.vue'
import { useJobsStore } from '../store'
import type { InterviewRound, ScheduleEvent } from '../types'

const router = useRouter()
const store = useJobsStore()

onMounted(() => store.ensureLoaded())

const eventVisible = ref(false)
const editingEvent = ref<ScheduleEvent | null>(null)

interface ScheduleItem {
  key: string
  kind: 'round' | 'event'
  scheduledAt: string // ISO 时间，用于排序与分组
  time: string // HH:mm
  typeLabel: string
  title: string
  location: string | null
  round?: InterviewRound
  event?: ScheduleEvent
  applicationId?: number | null
}

interface DateGroup {
  date: string
  isToday: boolean
  isTomorrow: boolean
  items: ScheduleItem[]
}

/** 有计划时间的流程轮次 → 日程项（按开始时间展示，老数据回退到截止时间） */
const roundItems = computed<ScheduleItem[]>(() => {
  const items: ScheduleItem[] = []
  for (const app of store.applications) {
    for (const round of app.rounds) {
      const when = round.startAt ?? round.scheduledAt
      if (when) {
        items.push({
          key: `round-${round.id}`,
          kind: 'round',
          scheduledAt: when,
          time: dayjs(when).format('HH:mm'),
          typeLabel: ROUND_TYPE_LABELS[round.roundType],
          title: `${app.company}${app.position ? ` · ${app.position}` : ''}`,
          location: null,
          round,
          applicationId: app.id,
        })
      }
    }
  }
  return items
})

/** 自定义日程 → 日程项 */
const eventItems = computed<ScheduleItem[]>(() =>
  store.events.map((e) => ({
    key: `event-${e.id}`,
    kind: 'event' as const,
    scheduledAt: e.eventTime,
    time: dayjs(e.eventTime).format('HH:mm'),
    typeLabel: EVENT_TYPE_LABELS[e.eventType],
    title: e.title,
    location: e.location,
    event: e,
    applicationId: e.applicationId,
  })),
)

/** 即将到来 = 时间 >= 今天 0 点（轮次 + 自定义日程合并，按天分组） */
const upcomingGroups = computed<DateGroup[]>(() => {
  const todayStart = dayjs().startOf('day')
  const upcoming = [...roundItems.value, ...eventItems.value].filter((i) =>
    dayjs(i.scheduledAt).isAfter(todayStart.subtract(1, 'ms')),
  )
  return groupByDate(upcoming)
})

/** 已过期待定 = 轮次时间已过且结果仍待定（自定义日程无结果概念，不参与） */
const pendingPastGroups = computed<DateGroup[]>(() => {
  const todayStart = dayjs().startOf('day')
  const past = roundItems.value.filter(
    (i) =>
      i.round!.result === 'pending' &&
      dayjs(i.scheduledAt).isBefore(todayStart.subtract(1, 'ms')),
  )
  return groupByDate(past).reverse()
})

function groupByDate(items: ScheduleItem[]): DateGroup[] {
  const map = new Map<string, ScheduleItem[]>()
  for (const item of items) {
    const date = dayjs(item.scheduledAt).format('YYYY-MM-DD dddd')
    if (!map.has(date)) map.set(date, [])
    map.get(date)!.push(item)
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, list]) => ({
      date,
      isToday: date === dayjs().format('YYYY-MM-DD dddd'),
      isTomorrow: date === dayjs().add(1, 'day').format('YYYY-MM-DD dddd'),
      items: list.sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt)),
    }))
}

/** 自定义日程关联投递的显示名（卡片灰字提示） */
function relAppName(item: ScheduleItem): string | null {
  if (item.kind !== 'event' || !item.applicationId) return null
  const app = store.applications.find((a) => a.id === item.applicationId)
  if (!app) return null
  return app.position ? `${app.company} · ${app.position}` : app.company
}

function openItem(item: ScheduleItem) {
  if (item.kind === 'round') {
    router.push(`/jobs/applications/${item.applicationId}`)
  } else {
    openEditEvent(item.event!)
  }
}

function openCreateEvent() {
  editingEvent.value = null
  eventVisible.value = true
}

function openEditEvent(event: ScheduleEvent) {
  editingEvent.value = event
  eventVisible.value = true
}

async function confirmRemoveEvent(event: ScheduleEvent) {
  const ok = await ElMessageBox.confirm(`确定删除日程「${event.title}」吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (ok) await store.removeEvent(event.id)
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint {
  color: #9ca3af;
  font-size: 12px;
  font-weight: 400;
}

.date-group {
  margin-bottom: 16px;
}

.date-title {
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-title.past {
  color: #9ca3af;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.schedule-card {
  cursor: pointer;
  --el-card-padding: 12px 16px;
}

.schedule-card.past {
  opacity: 0.7;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.time {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.title {
  color: #374151;
}

.rel {
  color: #9ca3af;
  font-size: 12px;
}

.location {
  color: #6b7280;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.spacer {
  flex: 1;
}
</style>