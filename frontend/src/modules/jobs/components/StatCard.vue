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
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(23, 24, 26, 0.04);
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(23, 24, 26, 0.08);
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
  font-size: 12px;
  font-weight: 500;
}

.value {
  margin-top: 6px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
  color: var(--ink);
}
</style>