<template>
  <el-tag :color="color" effect="dark" class="status-tag" disable-transitions>
    {{ label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { REJECT_STAGE_LABELS, STATUS_COLORS, STATUS_LABELS } from '../constants'
import type { ApplicationStatus } from '../types'

const props = defineProps<{
  status: ApplicationStatus
  /** 挂的阶段细分（rejected 时显示「一面挂」等替代文案） */
  rejectStage?: string | null
}>()

const label = computed(() =>
  props.status === 'rejected' && props.rejectStage
    ? REJECT_STAGE_LABELS[props.rejectStage] ?? STATUS_LABELS[props.status]
    : STATUS_LABELS[props.status],
)
const color = computed(() => STATUS_COLORS[props.status])
</script>

<style scoped>
.status-tag {
  border: none;
  color: #fff;
}
</style>