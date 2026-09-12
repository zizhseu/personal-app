<template>
  <el-tag :color="color" effect="dark" class="status-tag" disable-transitions>
    {{ label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { STATUS_COLORS, STATUS_LABELS } from '../constants'
import type { ApplicationStatus } from '../types'

const props = defineProps<{ status: ApplicationStatus }>()

const label = computed(() => STATUS_LABELS[props.status] ?? props.status)
const color = computed(() => STATUS_COLORS[props.status] ?? '#94A3B8')
</script>

<style scoped>
.status-tag {
  border: none;
  color: #fff;
  font-weight: 600;
  border-radius: 999px;
}
</style>