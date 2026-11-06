<template>
  <el-dropdown trigger="click" :disabled="unavailable" @command="changeStatus">
    <button
      type="button"
      class="position-status-trigger"
      :disabled="unavailable"
      :aria-label="`修改${positionLabel(position)}的状态`"
      :aria-busy="saving"
      title="点击修改该岗位状态"
      @click.stop
    >
      <StatusTag v-if="target?.status" :status="target.status" />
      <span v-else class="unrecorded-status">设置状态</span>
      <el-icon :class="{ 'is-loading': saving }">
        <Loading v-if="saving" />
        <CaretBottom v-else />
      </el-icon>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item v-for="status in STATUS_ORDER" :key="status" :command="status" :disabled="status === target?.status">
          {{ STATUS_LABELS[status] }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CaretBottom, Loading } from '@element-plus/icons-vue'
import StatusTag from './StatusTag.vue'
import { STATUS_LABELS, STATUS_ORDER } from '../constants'
import { recordedPosition } from '../positionResolution'
import { positionStatusPayload } from '../positionStatus'
import { positionLabel } from '../selectors'
import { useJobsStore } from '../store'
import type { ApplicationStatus } from '../types'

const props = defineProps<{ applicationId: number; position: string | null; positionVersion: number; disabled?: boolean }>()
const store = useJobsStore()
const application = computed(() => store.applications.find(item => item.id === props.applicationId))
const target = computed(() => application.value?.positionSummaries?.find(item =>
  item.positionVersion === props.positionVersion && recordedPosition(item.position) === recordedPosition(props.position)))
const key = computed(() => JSON.stringify([props.applicationId, props.positionVersion, recordedPosition(props.position)]))
const saving = computed(() => store.savingPositionStatusKeys.includes(key.value))
const unavailable = computed(() => props.disabled || saving.value || !target.value)

async function changeStatus(status: ApplicationStatus) {
  if (!application.value || !target.value || unavailable.value || status === target.value.status) return
  const payload = positionStatusPayload(application.value, target.value, status)
  try {
    await store.setPositionStatus(props.applicationId, payload)
  } catch { /* 请求层提示冲突或错误，状态文字保持已保存的值。 */ }
}
</script>

<style scoped>
.position-status-trigger { display: inline-flex; align-items: center; gap: 4px; padding: 3px 0; border: 0; background: transparent; color: var(--ink-3); font: inherit; cursor: pointer; }
.position-status-trigger:disabled { cursor: default; opacity: 0.65; }
.position-status-trigger:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 3px; border-radius: 3px; }
.unrecorded-status { font-size: 13px; }
</style>
