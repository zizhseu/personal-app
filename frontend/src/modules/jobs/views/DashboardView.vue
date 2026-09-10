<template>
  <div class="page">
    <!-- 统计卡片行 -->
    <el-row :gutter="16">
      <el-col v-for="card in statCards" :key="card.label" :span="6">
        <StatCard :value="card.value" :label="card.label" />
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16" class="charts">
      <el-col :span="10">
        <el-card shadow="never" class="chart-card">
          <template #header>状态分布</template>
          <VChart v-if="statusOption" :option="statusOption" autoresize class="chart pie" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="chart-header">
              <span>投递趋势</span>
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                value-format="YYYY-MM-DD"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                :shortcuts="trendShortcuts"
                :clearable="false"
                size="small"
                style="width: 280px"
              />
            </div>
          </template>
          <VChart v-if="trendOption" :option="trendOption" autoresize class="chart" />
          <el-empty v-else description="所选时间段内暂无投递" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="24">
        <el-card shadow="never" class="chart-card">
          <template #header>渠道分布</template>
          <VChart v-if="channelOption" :option="channelOption" autoresize class="chart channel" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import StatCard from '../components/StatCard.vue'
import { STATUS_COLORS, STATUS_LABELS, STATUS_ORDER } from '../constants'
import { useJobsStore } from '../store'
import type { ApplicationStatus } from '../types'

use([CanvasRenderer, PieChart, BarChart, TooltipComponent, LegendComponent, GridComponent])

const store = useJobsStore()

onMounted(() => store.ensureLoaded())

// ---------- 趋势图时间段 ----------
const dateRange = ref<[string, string]>([
  dayjs().subtract(6, 'day').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])

const trendShortcuts = [
  {
    text: '近一周',
    value: () => [dayjs().subtract(6, 'day').toDate(), dayjs().toDate()],
  },
  {
    text: '近一月',
    value: () => [dayjs().subtract(29, 'day').toDate(), dayjs().toDate()],
  },
  {
    text: '近三月',
    value: () => [dayjs().subtract(89, 'day').toDate(), dayjs().toDate()],
  },
]

// ---------- 统计卡片 ----------
const statCards = computed(() => {
  const apps = store.applications
  const weekAgo = dayjs().subtract(7, 'day')
  return [
    { label: '投递总数', value: apps.length },
    { label: '面试中', value: apps.filter((a) => a.status === 'interviewing').length },
    { label: 'Offer 数', value: apps.filter((a) => a.status === 'offer').length },
    {
      label: '本周新增',
      value: apps.filter((a) => a.applyDate && dayjs(a.applyDate).isAfter(weekAgo)).length,
    },
  ]
})

// ---------- 状态分布饼图（色板 = 状态语义色，与标签一致） ----------
const statusOption = computed(() => {
  const counts = STATUS_ORDER.map((s) => ({
    name: STATUS_LABELS[s],
    value: store.applications.filter((a) => a.status === s).length,
    itemStyle: { color: STATUS_COLORS[s as ApplicationStatus] },
  })).filter((d) => d.value > 0)
  if (counts.length === 0) return null
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c} 条（{d}%）' },
    legend: { bottom: 0, icon: 'circle', textStyle: { color: '#4b5563' } },
    series: [
      {
        type: 'pie',
        radius: ['0%', '68%'],
        center: ['50%', '46%'],
        // 2px 表面色间隔，扇区间有清晰分隔
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b} {c}', color: '#374151' },
        data: counts,
      },
    ],
  }
})

// ---------- 投递趋势（时间段可选；≤14 天按天聚合，更长按周聚合） ----------
const trendOption = computed(() => {
  const [startStr, endStr] = dateRange.value
  if (!startStr || !endStr) return null
  const rangeStart = dayjs(startStr).startOf('day')
  const rangeEnd = dayjs(endStr).endOf('day')
  if (rangeEnd.isBefore(rangeStart)) return null

  const totalDays = rangeEnd.diff(rangeStart, 'day') + 1
  const step = totalDays <= 14 ? 1 : 7

  // 从起始日期切桶：每天一桶或每 7 天一桶（末桶不满一周时截断到范围终点）
  const buckets: { label: string; start: Dayjs; end: Dayjs }[] = []
  let cursor = rangeStart
  while (cursor.isBefore(rangeEnd)) {
    const naturalEnd = cursor.add(step - 1, 'day')
    const bucketEnd = naturalEnd.isAfter(rangeEnd) ? rangeEnd : naturalEnd
    buckets.push({ label: cursor.format('M.D'), start: cursor, end: bucketEnd.endOf('day') })
    cursor = bucketEnd.add(1, 'day').startOf('day')
  }

  const counts = buckets.map((b) =>
    store.applications.filter((a) => {
      if (!a.applyDate) return false
      const d = dayjs(a.applyDate)
      return d.isAfter(b.start.subtract(1, 'ms')) && d.isBefore(b.end.add(1, 'ms'))
    }).length,
  )

  return {
    tooltip: { trigger: 'axis', formatter: '{b} ：{c} 条' },
    grid: { left: 32, right: 16, top: 20, bottom: 28 },
    xAxis: {
      type: 'category',
      data: buckets.map((b) => b.label),
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#6b7280' },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#f3f4f6' } },
    },
    series: [
      {
        type: 'bar',
        data: counts,
        barMaxWidth: 28,
        itemStyle: { color: '#3B82F6', borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})

// ---------- 渠道分布（横向条形图，全部同一色，长度已表达数量） ----------
const channelOption = computed(() => {
  const counts = new Map<string, number>()
  for (const a of store.applications) {
    const key = a.channel || '未填写'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  if (counts.size === 0) return null
  const sorted = [...counts.entries()].sort((x, y) => x[1] - y[1])
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c} 条' },
    grid: { left: 90, right: 40, top: 8, bottom: 24 },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#f3f4f6' } },
    },
    yAxis: {
      type: 'category',
      data: sorted.map(([name]) => name),
      axisLabel: { color: '#374151' },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [
      {
        type: 'bar',
        data: sorted.map(([, v]) => v),
        barMaxWidth: 18,
        itemStyle: { color: '#3B82F6', borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right', color: '#374151' },
      },
    ],
  }
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.charts {
  margin-top: 0;
}

.charts .el-col {
  margin-bottom: 16px;
}

.chart-card {
  border-radius: 8px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.chart {
  height: 280px;
}

.chart.pie {
  height: 300px;
}

.chart.channel {
  height: 240px;
}
</style>