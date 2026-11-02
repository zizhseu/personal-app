<template>
  <div v-if="app" class="page">
    <el-page-header class="header" @back="router.back()">
      <template #content>
        <div class="head-line">
          <span class="title">{{ app.company }}{{ app.position ? ` · ${app.position}` : '' }}</span>
          <el-dropdown
            v-if="hasActivePosition"
            trigger="click"
            @command="quickSetStatus"
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
          <span v-else class="inactive-position">暂无当前岗位</span>
        </div>
      </template>
    </el-page-header>

    <!-- 信息卡 -->
    <el-card shadow="never" class="info-card">
      <el-descriptions :column="narrow ? 1 : 3" border>
        <el-descriptions-item label="公司">{{ app.company }}</el-descriptions-item>
        <el-descriptions-item label="当前岗位">{{ hasActivePosition ? app.position ?? '未填写' : '暂无当前岗位' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag v-if="hasActivePosition" :status="app.status" />
          <span v-else>—</span>
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
        <el-button plain @click="positionVisible = true">{{ hasActivePosition ? '更换岗位' : '新增岗位' }}</el-button>
        <el-button type="primary" plain icon="Edit" @click="editVisible = true">编辑投递</el-button>
      </div>
    </el-card>

    <!-- 每次岗位流程独立成组，轮次与状态变化在组内展示。 -->
    <section class="position-section" aria-labelledby="position-history-title">
      <div class="section-heading">
        <div>
          <h2 id="position-history-title">岗位历程</h2>
          <p>按岗位查看流程轮次、状态变化与复盘</p>
        </div>
        <el-button v-if="positionGroups.length > 1" link type="primary" @click="toggleAllPositions">{{ allPositionsExpanded ? '仅展开当前' : '展开全部' }}</el-button>
      </div>
      <div v-if="positionGroups.length" class="position-list">
        <PositionHistoryGroup
          v-for="group in positionGroups"
          :key="`${app.id}:${group.key}`"
          :group="group"
          :expanded="expandedPositions.has(group.key)"
          :deleting="deletingPositionKey === group.key"
          @toggle="togglePosition(group.key)"
          @add-round="openAddRound(group)"
          @remove-position="confirmRemovePosition(group)"
          @edit-round="openEditRound"
          @remove-round="confirmRemoveRound"
          @edit-stage="editStagePosition"
          @remove-stage="removeStatusRow"
          @remove-result="removeResultRow"
        />
      </div>
      <el-empty v-else description="暂无岗位，新增后即可记录流程轮次与状态变化">
        <el-button type="primary" @click="positionVisible = true">新增岗位</el-button>
      </el-empty>
    </section>

    <ApplicationFormDialog v-model="editVisible" :application="app" />
    <PositionChangeDialog v-model="positionVisible" :application="app" />
    <RoundFormDialog v-model="roundVisible" :application-id="app.id" :round="editingRound" :target="roundTarget" />
  </div>

  <div v-else class="page">
    <el-skeleton :rows="6" animated />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { CaretBottom, Link } from '@element-plus/icons-vue'
import StatusTag from '../components/StatusTag.vue'
import ApplicationFormDialog from '../components/ApplicationFormDialog.vue'
import RoundFormDialog from '../components/RoundFormDialog.vue'
import PositionChangeDialog from '../components/PositionChangeDialog.vue'
import PositionHistoryGroup from '../components/PositionHistoryGroup.vue'
import { groupPositionHistory } from '../history'
import type { PositionHistoryGroup as PositionGroup } from '../history'
import { hasCurrentPosition, positionLabel } from '../selectors'
import { STATUS_LABELS, STATUS_ORDER } from '../constants'
import { useJobsStore } from '../store'
import type { ApplicationStatus, InterviewRound, RoundResultChange, RoundTarget, StatusHistory } from '../types'

const route = useRoute()
const router = useRouter()
const store = useJobsStore()
const narrow = ref(false)
const narrowQuery = window.matchMedia('(max-width: 760px)')
const syncNarrow = () => { narrow.value = narrowQuery.matches }
onMounted(() => { syncNarrow(); narrowQuery.addEventListener('change', syncNarrow) })
onBeforeUnmount(() => narrowQuery.removeEventListener('change', syncNarrow))

const editVisible = ref(false)
const positionVisible = ref(false)
const roundVisible = ref(false)
const editingRound = ref<InterviewRound | null>(null)
const roundTarget = ref<RoundTarget | null>(null)
const deletingPositionKey = ref<string | null>(null)
onMounted(() => store.ensureLoaded())
const app = computed(() => store.applications.find(row => row.id === Number(route.params.id)))
const hasActivePosition = computed(() => !!app.value && hasCurrentPosition(app.value))
const positionGroups = computed(() => app.value ? groupPositionHistory(app.value) : [])
const expandedPositions = ref(new Set<string>())
let expandedApplicationId: number | undefined
const allPositionsExpanded = computed(() => positionGroups.value.every(group => expandedPositions.value.has(group.key)))

watch(positionGroups, (groups, previousGroups) => {
  if (expandedApplicationId !== app.value?.id) {
    // 新打开详情时只展开当前岗位；同一详情内的刷新保留用户的展开选择。
    expandedApplicationId = app.value?.id
    const initial = groups.find(group => group.isCurrent) ?? groups[0]
    expandedPositions.value = new Set(initial ? [initial.key] : [])
    return
  }
  const keys = new Set(groups.map(group => group.key))
  const previousKeys = new Set((previousGroups ?? []).map(group => group.key))
  const expanded = new Set([...expandedPositions.value].filter(key => keys.has(key)))
  // 换岗位或补录导致新分组出现时，展开该组以显示刚保存的内容。
  for (const group of groups) if (!previousKeys.has(group.key)) expanded.add(group.key)
  if (!expanded.size && !groups.some(group => group.isCurrent) && groups[0]) expanded.add(groups[0].key)
  expandedPositions.value = expanded
}, { immediate: true })

function togglePosition(key: string) {
  const next = new Set(expandedPositions.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedPositions.value = next
}

function toggleAllPositions() {
  expandedPositions.value = new Set(positionGroups.value.filter(group => !allPositionsExpanded.value || group.isCurrent).map(group => group.key))
}

async function quickSetStatus(status: ApplicationStatus) {
  if (app.value) await store.quickSetStatus(app.value.id, status)
}

function openAddRound(target: RoundTarget) {
  editingRound.value = null
  roundTarget.value = { position: target.position, positionVersion: target.positionVersion, isCurrent: target.isCurrent, status: target.status }
  roundVisible.value = true
}

function openEditRound(round: InterviewRound) {
  roundTarget.value = null
  editingRound.value = round
  roundVisible.value = true
}

async function editStagePosition(stage: StatusHistory) {
  const position = await ElMessageBox.prompt('填写该阶段当时的岗位。会同步此阶段关联的轮次与结果记录，当前岗位保持不变。', '补录 / 更正历史岗位', {
    inputValue: stage.position ?? '', inputValidator: value => value.trim().length <= 100 || '岗位名称不能超过 100 字',
    confirmButtonText: '保存', cancelButtonText: '取消',
  }).then(result => result.value.trim() || null).catch(() => undefined)
  if (position !== undefined) await store.updateStatusPosition(stage.id, position)
}

async function removeStatusRow(stage: StatusHistory) {
  await store.removeStatusHistory(stage.id)
}

async function removeResultRow(result: RoundResultChange) {
  await store.removeResultHistory(result.id)
}

async function confirmRemoveRound(round: InterviewRound) {
  const ok = await ElMessageBox.confirm('确定删除这一轮吗？', '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  }).catch(() => false)
  if (ok) await store.removeRound(round.id)
}

async function confirmRemovePosition(group: PositionGroup) {
  if (!app.value || deletingPositionKey.value) return
  const applicationId = app.value.id
  const payload = { position: group.position, positionVersion: group.positionVersion, expectedPositionVersion: app.value.positionVersion }
  const consequence = group.isCurrent ? '当前岗位将留空，公司和其他岗位的历史保留。' : '公司和其他岗位的记录保留。'
  deletingPositionKey.value = group.key
  try {
    const ok = await ElMessageBox.confirm(
      `删除「${positionLabel(group.position)}」（第 ${group.positionVersion} 次流程）及其 ${group.rounds.length} 个轮次、${group.statusHistory.length} 条状态变化、${group.resultHistory.length} 条结果记录？${consequence}删除后无法撤销。`,
      '删除岗位', { type: 'warning', confirmButtonText: '删除岗位', cancelButtonText: '取消', customClass: 'position-delete-confirm' },
    ).then(() => true).catch(() => false)
    if (ok) await store.removePosition(applicationId, payload)
  } catch { /* 请求层提示错误，保留原岗位供用户核对。 */ }
  finally { deletingPositionKey.value = null }
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; min-width: 0; gap: 20px; }
.header { padding: 4px 0; }
.head-line { display: flex; align-items: center; gap: 10px; min-width: 0; flex-wrap: wrap; }
.title { min-width: 0; overflow-wrap: anywhere; font-size: 20px; font-weight: 700; letter-spacing: -0.01em; line-height: 1.3; }
.status-trigger { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.caret { color: var(--ink-3); font-size: 12px; }
.info-card { border-radius: 8px; }
.info-card :deep(.el-descriptions__content) { overflow-wrap: anywhere; }
.jd-link { display: inline-flex; align-items: center; gap: 2px; color: var(--el-color-primary); text-decoration: none; }
.jd-link:hover { text-decoration: underline; }
.link-icon { font-size: 12px; }
.info-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.position-section { min-width: 0; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.section-heading h2 { margin: 0; color: var(--ink); font-size: 16px; font-weight: 600; }
.section-heading p { margin: 5px 0 0; color: var(--ink-3); font-size: 13px; line-height: 1.6; }
.position-list { display: flex; flex-direction: column; gap: 12px; }
.inactive-position { color: var(--ink-3); font-size: 13px; }
:global(.position-delete-confirm) { width: 440px; max-width: calc(100vw - 32px); }
</style>
