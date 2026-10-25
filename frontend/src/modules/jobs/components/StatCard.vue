<template>
  <div class="stat-card">
    <div class="stat-head">
      <span v-if="dot" class="dot" :style="{ background: dot }" />
      <span class="label">{{ label }}</span>
    </div>
    <div class="value num">{{ value }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  value: number | string
  label: string
  /** 语义色点（可选），用于和状态色板呼应 */
  dot?: string
}>()
</script>

<style scoped>
.stat-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  padding: 20px;
  box-shadow: var(--shadow-sm);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.stat-card:hover {
  border-color: var(--el-color-primary-light-7);
  box-shadow: var(--shadow-md);
}

.stat-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.label {
  color: var(--ink-3);
  font-size: 13px;
  font-weight: 500;
}

.value {
  margin-top: 12px;
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  color: var(--ink);
}
</style>
