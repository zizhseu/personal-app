<template>
  <article class="position-group" :class="{ current: group.isCurrent }" :data-position="group.position ?? ''" :data-position-version="group.positionVersion">
    <h3 class="position-heading">
      <button class="position-toggle" :aria-expanded="expanded" :aria-controls="bodyId" @click="emit('toggle')">
        <span class="position-identity">
          <el-icon class="position-caret" :class="{ open: expanded }"><ArrowRight /></el-icon>
          <span class="position-name">{{ positionLabel(group.position) }}</span>
          <el-tag v-if="group.isCurrent" size="small" effect="plain">当前岗位</el-tag>
          <span class="process-label">第 {{ group.positionVersion }} 次流程</span>
        </span>
        <span class="position-summary">
          <StatusTag v-if="group.status" :status="group.status" />
          <span>{{ group.rounds.length }} 个轮次 · {{ group.statusHistory.length }} 次状态变化</span>
        </span>
      </button>
    </h3>

    <div v-show="expanded" :id="bodyId" class="position-body">
      <p v-if="!group.position" class="unknown-position">这些记录未保存岗位名称，可在轮次或状态变化中补录。</p>
      <div class="position-panels">
        <section class="rounds-panel" :aria-labelledby="`${bodyId}-rounds`">
          <div class="panel-heading">
            <h4 :id="`${bodyId}-rounds`">流程轮次 <span>（{{ group.rounds.length }}）</span></h4>
            <el-button type="primary" plain size="small" icon="Plus" @click="emit('addRound')">添加轮次</el-button>
          </div>
          <el-timeline v-if="group.rounds.length" class="timeline">
            <el-timeline-item v-for="round in group.rounds" :key="round.id" :timestamp="roundTimeText(round)" :type="timelineType(round.result)" :hollow="round.result === 'not_started'" placement="top">
              <div class="round-item" :data-round-id="round.id">
                <div class="round-head">
                  <span class="round-name">{{ ROUND_TYPE_LABELS[round.roundType] }}</span>
                  <el-tag size="small" effect="dark" disable-transitions class="result-tag" :color="RESULT_COLORS[round.result]">{{ RESULT_LABELS[round.result] }}</el-tag>
                  <span v-if="!round.position && group.position" class="snapshot-hint">岗位待补录</span>
                  <span class="round-actions">
                    <el-button link type="primary" size="small" @click="emit('editRound', round)">编辑</el-button>
                    <el-button link type="danger" size="small" @click="emit('removeRound', round)">删除</el-button>
                  </span>
                </div>
                <p v-if="round.resultChangedAt" class="round-result-time">结果更新于 {{ formatDateTime(round.resultChangedAt) }}</p>
                <p class="round-note" :class="{ empty: !round.reviewNote }">{{ round.reviewNote || '暂无复盘笔记' }}</p>
              </div>
            </el-timeline-item>
          </el-timeline>
          <p v-else class="empty-panel">{{ group.isCurrent ? '该岗位还没有流程轮次，可点击「添加轮次」记录。' : '该岗位没有流程轮次记录。' }}</p>
        </section>

        <section class="history-panel" :aria-labelledby="`${bodyId}-history`">
          <div class="panel-heading">
            <h4 :id="`${bodyId}-history`">状态变化 <span>（{{ group.statusHistory.length }}）</span></h4>
            <span class="header-hint">自动记录</span>
          </div>
          <div class="history-list">
            <div v-for="stage in group.statusHistory" :key="stage.id" class="history-group" :data-stage-id="stage.id">
              <div class="history-row">
                <button class="history-toggle" :disabled="!resultChangesOf(stage).length" :aria-expanded="resultChangesOf(stage).length ? expandedHistory.has(stage.id) : undefined" :aria-controls="resultChangesOf(stage).length ? `${bodyId}-stage-${stage.id}` : undefined" @click="toggleHistory(stage.id)">
                  <el-icon class="history-caret" :class="{ open: expandedHistory.has(stage.id), invisible: !resultChangesOf(stage).length }"><CaretRight /></el-icon>
                  <StatusTag :status="stage.status" />
                  <span v-if="resultChangesOf(stage).length" class="change-count">{{ resultChangesOf(stage).length }}</span>
                </button>
                <el-button link size="small" class="stage-position" :title="`补录或更正该阶段岗位：${positionLabel(stage.position)}`" @click="emit('editStage', stage)">{{ stage.position ? '更正岗位' : '补录岗位' }}</el-button>
                <time class="history-time">{{ formatDateTime(stage.changedAt) }}</time>
                <el-button link class="row-remove" :icon="Close" aria-label="删除此条状态记录" title="删除此条状态记录" @click="emit('removeStage', stage)" />
              </div>
              <div v-if="expandedHistory.has(stage.id)" :id="`${bodyId}-stage-${stage.id}`" class="result-changes">
                <div v-for="result in resultChangesOf(stage)" :key="result.id" class="result-change-row" :data-result-id="result.id">
                  <span class="rc-round">{{ roundTypeLabel(result.roundType) }}</span>
                  <el-tag size="small" effect="dark" disable-transitions class="result-tag" :color="RESULT_COLORS[result.toResult]">{{ RESULT_LABELS[result.toResult] }}</el-tag>
                  <time class="rc-time">{{ formatShortDateTime(result.changedAt) }}</time>
                  <el-button link class="row-remove" :icon="Close" aria-label="删除此条结果记录" title="删除此条结果记录" @click="emit('removeResult', result)" />
                </div>
              </div>
            </div>
            <p v-if="!group.statusHistory.length" class="empty-panel">该岗位没有状态变化记录。</p>
            <div v-if="group.unassignedResults.length" class="unassigned-results">
              <p class="unassigned-title">未归属阶段的结果记录</p>
              <div v-for="result in group.unassignedResults" :key="result.id" class="result-change-row" :data-result-id="result.id">
                <span class="rc-round">{{ roundTypeLabel(result.roundType) }}</span>
                <el-tag size="small" effect="dark" class="result-tag" :color="RESULT_COLORS[result.toResult]">{{ RESULT_LABELS[result.toResult] }}</el-tag>
                <time class="rc-time">{{ formatShortDateTime(result.changedAt) }}</time>
                <el-button link class="row-remove" :icon="Close" aria-label="删除此条结果记录" title="删除此条结果记录" @click="emit('removeResult', result)" />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowRight, CaretRight, Close } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import StatusTag from './StatusTag.vue'
import { positionLabel } from '../selectors'
import { ROUND_TYPE_LABELS, RESULT_LABELS, RESULT_COLORS } from '../constants'
import { formatDateTime } from '@/shared/utils/format'
import type { PositionHistoryGroup } from '../history'
import type { InterviewRound, RoundResultChange, RoundType, StatusHistory } from '../types'

const props = defineProps<{ group: PositionHistoryGroup; expanded: boolean }>()
const emit = defineEmits<{
  toggle: []
  addRound: []
  editRound: [round: InterviewRound]
  removeRound: [round: InterviewRound]
  editStage: [stage: StatusHistory]
  removeStage: [stage: StatusHistory]
  removeResult: [result: RoundResultChange]
}>()
const bodyId = computed(() => `position-process-${props.group.positionVersion}-${encodeURIComponent(props.group.position ?? '')}`)
const expandedHistory = ref(new Set<number>())
const resultChangesOf = (stage: StatusHistory) => props.group.resultGroups.get(stage.id) ?? []
const roundTypeLabel = (type: string) => ROUND_TYPE_LABELS[type as RoundType] ?? type
const formatShortDateTime = (value: string) => dayjs(value).format('MM-DD HH:mm')

function toggleHistory(id: number) {
  const next = new Set(expandedHistory.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedHistory.value = next
}

function timelineType(result: InterviewRound['result']): 'primary' | 'success' | 'danger' {
  return result === 'passed' ? 'success' : result === 'failed' ? 'danger' : 'primary'
}

/** 按原轮次时间展示安排，不改变服务端的轮次顺序。 */
function roundTimeText(round: InterviewRound): string {
  const start = round.startAt ?? round.scheduledAt
  const parts = start ? [formatDateTime(start)] : []
  if (round.startAt && round.scheduledAt && round.scheduledAt !== round.startAt) parts.push(`截止 ${formatDateTime(round.scheduledAt)}`)
  return parts.join(' · ') || '时间待定'
}
</script>

<style scoped>
.position-group {
  min-width: 0;
  border: 1px solid var(--el-border-color-light);
  border-left: 3px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
  overflow: hidden;
}
.position-group.current { border-left-color: var(--el-color-primary); }
.position-heading { margin: 0; font-size: inherit; }
.position-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border: 0;
  background: transparent;
  color: var(--ink);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.position-toggle:hover { background: var(--el-fill-color-light); }
.position-toggle:focus-visible, .history-toggle:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: -3px; }
.position-identity { display: flex; flex: 1; min-width: 0; align-items: center; flex-wrap: wrap; gap: 8px; }
.position-caret { flex-shrink: 0; font-size: 13px; color: var(--ink-3); transition: transform 0.15s ease; }
.position-caret.open { transform: rotate(90deg); }
.position-name { min-width: 0; font-size: 16px; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; }
.process-label, .position-summary, .header-hint, .snapshot-hint { color: var(--ink-3); font-size: 12px; font-weight: 400; }
.position-summary { display: flex; flex-shrink: 0; align-items: center; flex-wrap: wrap; gap: 12px; line-height: 1.6; }
.position-body { border-top: 1px solid var(--el-border-color-lighter); }
.unknown-position { margin: 0; padding: 12px 20px 0; color: var(--ink-3); font-size: 13px; line-height: 1.6; }
.position-panels { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); }
.rounds-panel, .history-panel { min-width: 0; padding: 20px; }
.history-panel { border-left: 1px solid var(--el-border-color-lighter); }
.panel-heading { min-height: 28px; display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.panel-heading h4 { margin: 0; color: var(--ink); font-size: 14px; font-weight: 600; }
.panel-heading h4 span { color: var(--ink-3); font-weight: 400; }
.timeline { margin: 0; padding-left: 6px; }
.round-head { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.round-name { font-weight: 600; }
.round-actions { display: inline-flex; margin-left: auto; }
.result-tag { border: 0; color: #fff; font-weight: 600; border-radius: 999px; flex-shrink: 0; }
.round-result-time { margin: 6px 0 0; color: var(--ink-3); font-size: 12px; }
.round-note { margin: 6px 0 0; color: var(--ink-2); white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 1.7; }
.empty, .empty-panel { color: var(--ink-3); }
.empty-panel { margin: 0; font-size: 13px; line-height: 1.8; }
.history-group + .history-group { border-top: 1px solid var(--el-border-color-lighter); }
.history-row { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; gap: 8px; padding: 10px 0; }
.history-toggle { display: inline-flex; align-items: center; gap: 6px; padding: 3px 0; background: none; border: 0; color: inherit; font: inherit; cursor: pointer; }
.history-toggle:disabled { cursor: default; }
.history-caret { color: var(--ink-3); font-size: 12px; transition: transform 0.15s ease; }
.history-caret.open { transform: rotate(90deg); }
.invisible { visibility: hidden; }
.change-count { color: var(--ink-3); font-size: 12px; }
.stage-position { color: var(--ink-3); }
.history-time { margin-left: auto; color: var(--ink-2); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.row-remove { flex-shrink: 0; margin-left: 0; color: var(--ink-3); }
.row-remove:hover { color: var(--el-color-danger); }
.result-changes { display: flex; flex-direction: column; gap: 4px; margin-left: 6px; padding: 0 0 10px 12px; border-left: 2px solid var(--el-border-color-lighter); }
.result-change-row { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; gap: 8px; padding: 4px 0; }
.rc-round { color: var(--ink-2); font-size: 12px; overflow-wrap: anywhere; }
.rc-time { margin-left: auto; color: var(--ink-3); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.unassigned-results { margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--el-border-color-light); }
.unassigned-title { margin: 0 0 6px; color: var(--ink-3); font-size: 12px; }
@media (max-width: 1100px) {
  .position-panels { grid-template-columns: minmax(0, 1fr); }
  .history-panel { border-left: 0; border-top: 1px solid var(--el-border-color-lighter); }
}
@media (max-width: 700px) {
  .position-toggle { flex-direction: column; align-items: stretch; gap: 10px; padding: 14px; }
  .position-summary { margin-left: 21px; gap: 10px; }
  .rounds-panel, .history-panel { padding: 16px 14px; }
  .unknown-position { padding: 12px 14px 0; }
  .history-time { white-space: normal; }
}
@media (prefers-reduced-motion: reduce) {
  .position-caret, .history-caret { transition: none; }
}
</style>
