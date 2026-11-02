<template>
  <el-select
    class="primary-position-select"
    :model-value="selectedKey"
    :aria-label="`${application?.company ?? ''}的主要岗位`"
    :loading="saving"
    :disabled="disabled || saving || !choices.length"
    placeholder="暂无岗位"
    title="点击选择主要岗位，选中后自动保存"
    @click.stop
    @change="selectPosition"
  >
    <el-option v-for="choice in choices" :key="choice.key" :value="choice.key" :label="choice.label">
      <span>{{ positionLabel(choice.position) }}</span>
      <span class="choice-order">岗位记录 {{ choice.displayOrder }}</span>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { groupPositionHistory } from '../history'
import { positionLabel } from '../selectors'
import { useJobsStore } from '../store'

const props = defineProps<{ applicationId: number; disabled?: boolean }>()
const store = useJobsStore()
// 从原始投递取当前版本，不能使用列表投影中所选历史岗位的版本。
const application = computed(() => store.applications.find(item => item.id === props.applicationId))
const choices = computed(() => {
  const groups = application.value ? groupPositionHistory(application.value) : []
  return groups.map(group => ({ ...group, label: groups.filter(item => item.position === group.position).length > 1
    ? `${positionLabel(group.position)}（记录 ${group.displayOrder}）` : positionLabel(group.position) }))
    .sort((left, right) => left.displayOrder - right.displayOrder)
})
const selectedKey = computed(() => choices.value.find(item => item.isPrimary)?.key)
const saving = computed(() => store.savingPrimaryIds.includes(props.applicationId))

async function selectPosition(key: string) {
  const source = application.value
  const choice = choices.value.find(item => item.key === key)
  if (!source || !choice || key === selectedKey.value || saving.value) return
  try {
    await store.setPrimaryPosition(source.id, {
      position: choice.position,
      positionVersion: choice.positionVersion,
      expectedPositionVersion: source.positionVersion,
    })
  } catch { /* 请求层提示错误，保留已保存的选择。 */ }
}
</script>

<style scoped>
.primary-position-select { width: 100%; min-width: 0; }
.choice-order { margin-left: 16px; color: var(--ink-3); font-size: 12px; }
</style>
