<template>
  <el-card shadow="never" class="stat-card">
    <div class="value">{{ value }}</div>
    <div class="label">{{ label }}</div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  value: number | string
  label: string
}>()
</script>

<style scoped>
.stat-card {
  text-align: center;
}

.value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
}

.label {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}
</style>