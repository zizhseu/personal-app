<template>
  <div v-if="app" class="page">
    <el-page-header class="header" @back="router.back()">
      <template #content>
        <div class="head-line">
          <span class="title">{{ app.company }}{{ app.position ? ` · ${app.position}` : '' }}</span>
          <el-dropdown
            trigger="click"
            @command="(s: ApplicationStatus) => store.quickSetStatus(app.id, s)"
          >
            <span class="status-trigger" title="点击修改状态">
              <StatusTag :status="app.status" />
              <el-icon class="caret"><CaretBottom /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="s in STATUS_ORDER"
                  :key="s"
                  :command="s"
                  :disabled="s === app.status"
                >
                  {{ STATUS_LABELS[s] }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>
    </el-page-header>

    <!-- 信息卡 -->
    <el-card shadow="never" class="info-card">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="公司">{{ app.company }}</el-descriptions-item>
        <el-descriptions-item label="岗位">{{ app.position ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="app.status" />
        </el-descriptions-item>
        <el-descriptions-item label="投递链接">
          <a
            v-if="app.url"
            :href="app.url"
            target="_blank"
            rel="noopener noreferrer"
            class="jd-link"
          >
            打开招聘页面
            <el-icon class="link-icon"><Link /></el-icon>
          </a>
          <span v-else>—</span>
        </el-descriptions-item>
        <el-descriptions-item label="投递日期">{{ app.applyDate ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="薪资范围">{{ app.salary ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="Base">
          {{ app.base?.length ? app.base.join(' / ') : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">
          {{ app.note || '—' }}
        </el-descriptions-item>
      </el-descriptions>
      <div class="info-actions">
        <el-button type="primary" plain icon="Edit" @click="editVisible = true">编辑投递</el-button>
      </div>
    </el-card>

    <!-- 流程轮次 + 状态变化（左右并列） -->
    <div class="bottom-row">
      <el-card shadow="never" class="rounds-card">
        <template #header>
          <div class="card-header">
            <span>流程轮次（{{ app.rounds.length }}）</span>
            <el-button type="primary" icon="Plus" @click="openAddRound">添加轮次</el-button>
          </div>
        </template>

        <el-timeline v-if="app.rounds.length > 0" class="timeline">
          <el-timeline-item
            v-for="round in app.rounds"
            :key="round.id"
            :timestamp="roundTimeText(round)"
            :type="timelineType(round.result)"
            :hollow="round.result === 'not_started'"
            placement="top"
          >
            <div class="round-item">
              <div class="round-head">
                <span class="round-name">{{ ROUND_TYPE_LABELS[round.roundType] }}</span>
                <el-tag
                  :color="RESULT_COLORS[round.result]"
                  effect="dark"
                  size="small"
                  disable-transitions
                  class="result-tag"
                >
                  {{ RESULT_LABELS[round.result] }}
                </el-tag>
                <span class="round-actions">
                  <el-button link type="primary" size="small" @click="openEditRound(round)">
                    编辑
                  </el-button>
                  <el-button link type="danger" size="small" @click="confirmRemoveRound(round)">
                    删除
                  </el-button>
                </span>
              </div>
              <div v-if="round.reviewNote" class="round-note">{{ round.reviewNote }}</div>
              <div v-else class="round-note empty">暂无复盘笔记</div>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty
          v-else
          description="还没有流程轮次，点击右上角「添加轮次」记录测评 / 笔试 / 面试安排"
        />
      </el-card>

      <!-- 状态变化 -->
      <el-card v-if="app.statusHistory.length > 0" shadow="never" class="history-card">
        <template #header>
          <div class="card-header">
            <span>状态变化</span>
            <span class="header-hint">自动记录</span>
          </div>
        </template>
        <div class="history-list">
          <div v-for="h in app.statusHistory" :key="h.id" class="history-row">
            <StatusTag :status="h.status" />
            <span class="history-time">{{ formatDateTime(h.changedAt) }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <ApplicationFormDialog v-model="editVisible" :application="app" />
    <RoundFormDialog v-model="roundVisible" :application-id="app.id" :round="editingRound" />
  </div>

  <div v-else class="page">
    <el-skeleton :rows="6" animated />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import StatusTag from '../components/StatusTag.vue'
import ApplicationFormDialog from '../components/ApplicationFormDialog.vue'
import RoundFormDialog from '../components/RoundFormDialog.vue'
import { ROUND_TYPE_LABELS, RESULT_LABELS, RESULT_COLORS, STATUS_LABELS, STATUS_ORDER } from '../constants'
import { formatDateTime } from '@/shared/utils/format'
import { useJobsStore } from '../store'
import type { ApplicationStatus, InterviewRound } from '../types'

const route = useRoute()
const router = useRouter()
const store = useJobsStore()

const editVisible = ref(false)
const roundVisible = ref(false)
const editingRound = ref<InterviewRound | null>(null)

onMounted(() => store.ensureLoaded())

const app = computed(() =>
  store.applications.find((a) => a.id === Number(route.params.id)),
)

function timelineType(result: InterviewRound['result']): 'primary' | 'success' | 'danger' {
  if (result === 'passed') return 'success'
  if (result === 'failed') return 'danger'
  return 'primary'
}

/** 时间线时间文本：开始 · 截止（截止与开始相同则只显示一个） */
function roundTimeText(round: InterviewRound): string {
  const start = round.startAt ?? round.scheduledAt
  const parts: string[] = []
  if (start) parts.push(formatDateTime(start))
  if (round.startAt && round.scheduledAt && round.scheduledAt !== round.startAt) {
    parts.push(`截止 ${formatDateTime(round.scheduledAt)}`)
  }
  return parts.join(' · ') || '时间待定'
}

function openAddRound() {
  editingRound.value = null
  roundVisible.value = true
}

function openEditRound(round: InterviewRound) {
  editingRound.value = round
  roundVisible.value = true
}

async function confirmRemoveRound(round: InterviewRound) {
  const ok = await ElMessageBox.confirm('确定删除这一轮吗？', '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (ok) await store.removeRound(round.id)
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  padding: 4px 0;
}

.head-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.caret {
  color: var(--ink-3);
  font-size: 12px;
}

.title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.3;
}

/* 轮次（左）+ 状态变化（右）并列；窗口太窄时换行堆叠 */
.bottom-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.info-card,
.rounds-card,
.history-card {
  border-radius: 8px;
}

.rounds-card {
  flex: 1;
  min-width: 560px;
}

.history-card {
  width: 320px;
  flex-shrink: 0;
}

.jd-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--el-color-primary);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}

.link-icon {
  font-size: 12px;
}

.info-actions {
  margin-top: 14px;
  text-align: right;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-hint {
  color: #9ca3af;
  font-size: 12px;
  font-weight: 400;
}

.history-list {
  display: flex;
  flex-direction: column;
}

.history-row {
  /* 状态列固定宽、时间列跟随：两列各自垂直对齐 */
  display: grid;
  grid-template-columns: 88px 1fr;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.history-row :deep(.el-tag) {
  justify-self: start;
}

.history-row + .history-row {
  border-top: 1px solid var(--el-border-color-lighter);
}

.history-time {
  color: #6b7280;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.round-item {
  padding-bottom: 4px;
}

.round-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.round-name {
  font-weight: 600;
}

.result-tag {
  border: none;
  color: #fff;
  font-weight: 600;
  border-radius: 999px;
}

.round-actions {
  margin-left: auto;
}

.round-note {
  margin-top: 6px;
  color: #4b5563;
  white-space: pre-wrap;
  font-size: 13px;
}

.round-note.empty {
  color: #9ca3af;
}
</style>