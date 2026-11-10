<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h1>日程</h1>
        <p class="sub">按开始时间排列 · 轮次点击查看详情，日程点击可编辑</p>
      </div>
      <div class="actions">
        <el-button type="primary" icon="Plus" @click="openCreateEvent">新增日程</el-button>
      </div>
    </div>

    <!-- 待办：没做的 + 还没到时间的 -->
    <ScheduleList
      title="待办"
      empty-text="暂无待办事项，点击右上角「新增日程」添加宣讲会等安排"
      :items="schedule.todo"
      :now="now"
      colored
      @open="openItem"
      @edit-event="openEditEvent"
      @remove-event="confirmRemoveEvent"
    />

    <!-- 已办：已完成 / 已出结果 / 已过时间的 -->
    <ScheduleList
      title="已办"
      empty-text="还没有办完的事项"
      :items="schedule.done"
      :now="now"
      @open="openItem"
      @edit-event="openEditEvent"
      @remove-event="confirmRemoveEvent"
    />

    <!-- 过期：截止已过还没开始的 -->
    <ScheduleList
      title="过期"
      empty-text="没有过期任务，继续保持 👍"
      :items="schedule.expired"
      :now="now"
      danger
      @open="openItem"
      @edit-event="openEditEvent"
      @remove-event="confirmRemoveEvent"
    />

    <EventFormDialog v-model="eventVisible" :event="editingEvent" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import ScheduleList from '../components/ScheduleList.vue'
import EventFormDialog from '../components/EventFormDialog.vue'
import { useJobsStore } from '../store'
import { createScheduleGroups } from '../schedule'
import type { ScheduleEvent, ScheduleItem } from '../types'

const router = useRouter()
const store = useJobsStore()

const now = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval> | undefined
onMounted(async () => {
  clockTimer = setInterval(() => {
    now.value = Date.now()
  }, 60_000)
  await store.loadAll()
})
onBeforeUnmount(() => {
  if (clockTimer !== undefined) clearInterval(clockTimer)
})

const eventVisible = ref(false)
const editingEvent = ref<ScheduleEvent | null>(null)

const schedule = computed(() => createScheduleGroups(store.applications, store.events, now.value))

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
