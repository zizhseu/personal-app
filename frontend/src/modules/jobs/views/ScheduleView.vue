<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h1>日程</h1>
        <p class="sub">按截止时间排列 · 轮次点击查看详情，日程点击可编辑</p>
      </div>
      <div class="actions">
        <el-button type="primary" icon="Plus" @click="openCreateEvent">新增日程</el-button>
      </div>
    </div>

    <!-- 待办：没做的 + 还没到时间的 -->
    <ScheduleList
      title="待办"
      empty-text="暂无待办事项，点击右上角「新增日程」添加宣讲会等安排"
      :items="todoItems"
      colored
      @open="openItem"
      @edit-event="openEditEvent"
      @remove-event="confirmRemoveEvent"
    />

    <!-- 已办：已完成 / 已出结果 / 已过时间的 -->
    <ScheduleList
      title="已办"
      empty-text="还没有办完的事项"
      :items="doneItems"
      @open="openItem"
      @edit-event="openEditEvent"
      @remove-event="confirmRemoveEvent"
    />

    <!-- 过期：截止已过还没开始的 -->
    <ScheduleList
      title="过期"
      empty-text="没有过期任务，继续保持 👍"
      :items="expiredItems"
      danger
      @open="openItem"
      @edit-event="openEditEvent"
      @remove-event="confirmRemoveEvent"
    />

    <EventFormDialog v-model="eventVisible" :event="editingEvent" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { ROUND_TYPE_LABELS, EVENT_TYPE_LABELS } from '../constants'
import ScheduleList from '../components/ScheduleList.vue'
import EventFormDialog from '../components/EventFormDialog.vue'
import { useJobsStore } from '../store'
import type { RoundResult, ScheduleItem } from '../types'

const router = useRouter()
const store = useJobsStore()

onMounted(() => store.ensureLoaded())

const eventVisible = ref(false)
const editingEvent = ref<ScheduleEvent | null>(null)

const todayStart = () => dayjs().startOf('day')

/** 已办对应的轮次结果（做过 / 有结果） */
const DONE_RESULTS: RoundResult[] = ['completed', 'passed', 'failed', 'not_attended']

/** 有计划时间的流程轮次 → 日程项（展示与排序用截止时间，老数据回退开始时间） */
const roundItems = computed<ScheduleItem[]>(() => {
  const items: ScheduleItem[] = []
  for (const app of store.applications) {
    for (const round of app.rounds) {
      const when = round.scheduledAt ?? round.startAt
      if (when) {
        // 已有结果的轮次显示实际完成时间，否则显示截止时间
        const displayTime =
          round.result !== 'not_started' && round.resultChangedAt
            ? round.resultChangedAt
            : when
        items.push({
          key: `round-${round.id}`,
          kind: 'round',
          scheduledAt: when,
          doneAt: round.result !== 'not_started' ? round.resultChangedAt : null,
          time: dayjs(displayTime).format('MM-DD HH:mm'),
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
    doneAt: null,
    time: dayjs(e.eventTime).format('MM-DD HH:mm'),
    typeLabel: EVENT_TYPE_LABELS[e.eventType],
    title: e.title,
    location: e.location,
    event: e,
    applicationId: e.applicationId,
  })),
)

/** 待办：未开始的轮次（截止未过）+ 还没到时间的日程，按时间升序 */
const todoItems = computed<ScheduleItem[]>(() => {
  const start = todayStart()
  const rounds = roundItems.value.filter(
    (i) =>
      i.round!.result === 'not_started' &&
      dayjs(i.round!.scheduledAt ?? i.scheduledAt).isAfter(start.subtract(1, 'ms')),
  )
  const events = eventItems.value.filter((i) =>
    dayjs(i.scheduledAt).isAfter(start.subtract(1, 'ms')),
  )
  return [...rounds, ...events].sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt))
})

/** 已办：已出结果 / 已完成的轮次 + 已过时间的日程，按实际完成时间最近的在前 */
const doneItems = computed<ScheduleItem[]>(() => {
  const start = todayStart()
  const rounds = roundItems.value.filter((i) => DONE_RESULTS.includes(i.round!.result))
  const events = eventItems.value.filter(
    (i) => !dayjs(i.scheduledAt).isAfter(start.subtract(1, 'ms')),
  )
  return [...rounds, ...events].sort((a, b) =>
    (b.doneAt ?? b.scheduledAt).localeCompare(a.doneAt ?? a.scheduledAt),
  )
})

/** 过期：截止已过还没开始（已完成的不算过期），最近的在前 */
const expiredItems = computed<ScheduleItem[]>(() =>
  roundItems.value
    .filter(
      (i) =>
        i.round!.result === 'not_started' &&
        i.round!.scheduledAt &&
        dayjs(i.round!.scheduledAt).isBefore(todayStart().subtract(1, 'ms')),
    )
    .sort((a, b) => b.scheduledAt.localeCompare(a.scheduledAt)),
)

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
  gap: 18px;
}
</style>