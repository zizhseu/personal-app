<template>
  <div class="page">
    <!-- 页头 + 操作 -->
    <div class="page-head">
      <div>
        <h1>投递列表</h1>
        <p class="sub">{{ filtered.length }} 条记录 · 点击行查看详情</p>
      </div>
      <div class="actions">
        <el-button type="primary" icon="Plus" @click="openCreate">新增投递</el-button>
      </div>
    </div>

    <!-- 列表 -->
    <el-card shadow="never" class="table-card">
    <div class="table-toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索公司 / 岗位"
        :maxlength="500"
        clearable
        prefix-icon="Search"
        style="width: 260px"
      />
      <el-button @click="view.reset()">重置筛选</el-button>
    </div>
    <el-table
      ref="tableRef"
      v-loading="store.loading"
      :data="paged"
      row-key="id"
      :default-sort="tableSort"
      @sort-change="onSortChange"
      @filter-change="onFilterChange"
      @row-click="goDetail"
    >
      <el-table-column prop="company" label="公司" min-width="140" sortable="custom" fixed="left">
        <template #default="{ row }">
          <span class="company">{{ row.company }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="position" label="岗位" min-width="150" sortable="custom">
        <template #default="{ row }">{{ row.position ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="链接" width="80" align="center">
        <template #default="{ row }">
          <a
            v-if="row.url"
            :href="row.url"
            target="_blank"
            rel="noopener noreferrer"
            class="channel-link"
            :title="`打开 ${row.company} 的招聘页面`"
            @click.stop
          >
            打开
            <el-icon class="link-icon"><Link /></el-icon>
          </a>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="applyDate" label="投递日期" width="120" sortable="custom">
        <template #default="{ row }">{{ row.applyDate ?? '—' }}</template>
      </el-table-column>
      <el-table-column prop="deadline" label="截止时间" width="125" sortable="custom">
        <template #default="{ row }">
          {{ row.deadline ? dayjs(row.deadline).format('MM-DD HH:mm') : '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="salary" label="薪资" width="120">
        <template #default="{ row }">{{ row.salary ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="Base" width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <!-- 点击弹出城市多选，勾选即保存 -->
          <el-popover placement="bottom" :width="240" trigger="click">
            <template #reference>
              <span class="base-trigger" @click.stop>
                <span :class="{ 'base-empty': !row.base?.length }">
                  {{ row.base?.length ? row.base.join(' / ') : '选择' }}
                </span>
                <el-icon class="caret"><CaretBottom /></el-icon>
              </span>
            </template>
            <el-checkbox-group v-model="row.base" @change="saveBase(row)">
              <div class="base-options">
                <el-checkbox v-for="c in baseCheckboxOptions(row)" :key="c" :value="c">
                  {{ c }}
                </el-checkbox>
              </div>
            </el-checkbox-group>
            <div class="base-add">
              <el-input
                v-model="newCity"
                size="small"
                placeholder="其他城市，回车添加"
                @keyup.enter="addCity(row)"
              />
              <el-button size="small" type="primary" plain @click="addCity(row)">添加</el-button>
            </div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column
        label="状态"
        width="160"
        column-key="status"
        :filters="statusFilters"
        :filter-method="filterStatusMethod"
        :filtered-value="statusFilter"
        filter-placement="bottom-end"
      >
        <template #default="{ row }">
          <el-dropdown trigger="click" @command="(s: ApplicationStatus) => store.quickSetStatus(row.id, s)">
            <span class="status-trigger" @click.stop>
              <StatusTag :status="row.status" />
              <el-icon class="caret"><CaretBottom /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="s in STATUS_ORDER"
                  :key="s"
                  :command="s"
                  :disabled="s === row.status"
                >
                  {{ STATUS_LABELS[s] }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
      <el-table-column
        label="结果"
        width="110"
        column-key="result"
        :filters="resultFilters"
        :filter-method="filterResultMethod"
        :filtered-value="resultFilter"
        filter-placement="bottom-end"
      >
        <template #default="{ row }">
          <!-- 可点击下拉：非 Offer 态改最新轮次结果；Offer 态改接受 / 拒绝 -->
          <el-dropdown
            v-if="resultDisplay(row)"
            trigger="click"
            @command="(r: RoundResult) => quickSetResult(row, r)"
          >
            <span class="result-trigger" @click.stop>
              <el-tag
                :color="resultDisplay(row)!.color"
                effect="dark"
                size="small"
                disable-transitions
                class="result-tag"
              >
                {{ resultDisplay(row)!.label }}
              </el-tag>
              <el-icon class="caret"><CaretBottom /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="r in resultOptions(row)"
                  :key="r"
                  :command="r"
                  :disabled="r === currentResult(row)"
                >
                  {{ RESULT_LABELS[r] }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
          <el-button link type="primary" @click.stop="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click.stop="confirmRemove(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无投递记录，点击右上角「新增投递」开始记录" />
      </template>
    </el-table>
    <div class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        :page-size="PAGE_SIZE"
        :total="sorted.length"
        :pager-count="7"
        background
        layout="total, prev, pager, next, jumper"
      />
    </div>
    </el-card>

    <ApplicationFormDialog
      v-model="formVisible"
      :application="editing"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, toRefs, watch } from 'vue'
import { ElMessageBox, type TableInstance } from 'element-plus'
import dayjs from 'dayjs'
import StatusTag from '../components/StatusTag.vue'
import ApplicationFormDialog from '../components/ApplicationFormDialog.vue'
import { STATUS_LABELS, STATUS_ORDER, BASE_OPTIONS, RESULT_LABELS, RESULT_COLORS, NORMAL_RESULT_OPTIONS, OFFER_RESULT_OPTIONS } from '../constants'
import { useJobsStore } from '../store'
import { currentResult, latestRound } from '../selectors'
import type { Application, ApplicationStatus, RoundResult } from '../types'
import { useListViewState } from '@/shared/composables/useListViewState'
import { choiceField, listField, pageField, textField } from '@/shared/state/pageState'

const store = useJobsStore()

const PAGE_SIZE = 10
const view = useListViewState({
  q: textField(), status: listField<ApplicationStatus>(STATUS_ORDER),
  result: listField<RoundResult>(Object.keys(RESULT_LABELS) as RoundResult[]),
  sort: choiceField('applyDate', ['company', 'position', 'applyDate', 'deadline']),
  order: choiceField('desc', ['asc', 'desc', 'none']), page: pageField(),
}, { routes: ['jobs-list'], ready: () => store.loaded && !store.loading, count: (): number => sorted.value.length, pageSize: PAGE_SIZE })
const { q: keyword, status: statusFilter, result: resultFilter, sort: sortBy, order: sortOrder, page } = toRefs(view.state)

/** 表头状态筛选（勾选值由 el-table 的 filter-change 事件同步） */
const statusFilters = STATUS_ORDER.map((s) => ({ text: STATUS_LABELS[s], value: s }))

/** 表头结果筛选（选项 = 全部结果枚举） */
const resultFilters = (Object.keys(RESULT_LABELS) as RoundResult[]).map((r) => ({
  text: RESULT_LABELS[r],
  value: r,
}))

/** 排序与分页（EP 内置排序只作用于当前页，故在数据层接管） */
const sortState = computed(() => ({ prop: sortBy.value, order: sortOrder.value === 'none' ? null : sortOrder.value }))
const tableRef = ref<TableInstance>()
const tableSort = computed<{ prop: string; order?: 'ascending' | 'descending' }>(() => ({
  prop: sortBy.value, order: sortOrder.value === 'none' ? undefined : sortOrder.value === 'asc' ? 'ascending' : 'descending',
}))

const formVisible = ref(false)
const editing = ref<Application | null>(null)

/** Base 浮层里的自定义城市输入 */
const newCity = ref('')

onMounted(() => store.ensureLoaded())

/** 常驻选项 + 已选的自定义城市（保证已选项可取消） */
function baseCheckboxOptions(row: ListRow): string[] {
  return [...BASE_OPTIONS, ...row.base.filter((c) => !BASE_OPTIONS.includes(c))]
}

function addCity(row: ListRow) {
  const city = newCity.value.trim()
  if (!city) return
  if (!row.base.includes(city)) {
    row.base.push(city)
    void saveBase(row)
  }
  newCity.value = ''
}

/** 筛选 + 搜索（数据量小，全部前端现算） */
const filtered = computed(() => {
  let list = store.applications
  if (keyword.value) {
    const k = keyword.value.toLowerCase()
    // 岗位是选填字段（可空），必须可选链，否则空岗位的行会让整个过滤抛错、页面更新冻结
    list = list.filter(
      (a) =>
        a.company.toLowerCase().includes(k) || !!a.position?.toLowerCase().includes(k),
    )
  }
  if (statusFilter.value.length) {
    list = list.filter((a) => statusFilter.value.includes(a.status))
  }
  if (resultFilter.value.length) {
    list = list.filter((a) => {
      // 按「结果列显示的值」筛选：Offer 态看 Offer 决定，其余看最新轮次结果
      const disp = currentResult(a)
      return disp !== null && resultFilter.value.includes(disp)
    })
  }
  return list
})

/** 截止时间 = 流程轮次中最新的计划时间 */
function latestRoundTime(a: Application): string | null {
  const times = a.rounds.map((r) => r.scheduledAt).filter((t): t is string => !!t)
  return times.length ? times.reduce((m, t) => (t > m ? t : m)) : null
}

/** 列表行 = 筛选结果 + 现算的截止时间与最新轮次结果 */
const rows = computed(() =>
  filtered.value.map((a) => ({
    ...a,
    deadline: latestRoundTime(a),
    latestResult: latestRound(a)?.result ?? null,
    base: a.base ?? [],
  })),
)

type ListRow = Application & {
  deadline: string | null
  latestResult: RoundResult | null
  base: string[]
}

/** 数据层排序（EP 内置排序只作用于当前页，分页后必须自己排） */
const sorted = computed(() => {
  const { prop, order } = sortState.value
  if (!order) return rows.value
  const dir = order === 'asc' ? 1 : -1
  return [...rows.value].sort((a: ListRow, b: ListRow) => {
    if (prop === 'deadline') {
      return dir * (a.deadline ?? '9999').localeCompare(b.deadline ?? '9999')
    }
    const av = prop in a ? String(a[prop as keyof ListRow] ?? '') : ''
    const bv = prop in b ? String(b[prop as keyof ListRow] ?? '') : ''
    return dir * av.localeCompare(bv, 'zh')
  })
})

/** 当前页数据 */
const paged = computed(() =>
  sorted.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE),
)

function onSortChange({ prop, order }: { prop?: string; order: 'ascending' | 'descending' | null }) {
  if (prop && ['company', 'position', 'applyDate', 'deadline'].includes(prop)) sortBy.value = prop as typeof sortBy.value
  sortOrder.value = order === 'ascending' ? 'asc' : order === 'descending' ? 'desc' : 'none'
}

function onFilterChange(f: Record<string, ApplicationStatus[] | RoundResult[]>) {
  if ('status' in f) statusFilter.value = (f.status as ApplicationStatus[]) ?? []
  if ('result' in f) resultFilter.value = (f.result as RoundResult[]) ?? []
}

// Element Plus 的 default-sort 只负责初次挂载，历史导航恢复时同步表头指示。
watch([sortBy, sortOrder], async () => {
  await nextTick()
  if (sortOrder.value === 'none') tableRef.value?.clearSort()
  else tableRef.value?.sort(sortBy.value, sortOrder.value === 'asc' ? 'ascending' : 'descending')
}, { flush: 'post' })

/** EP 侧过滤与数据层过滤同条件，幂等 */
function filterStatusMethod(value: ApplicationStatus, row: ListRow) {
  return row.status === value
}

function filterResultMethod(value: RoundResult, row: ListRow) {
  return currentResult(row) === value
}

/** 结果列显示：Offer 态显示 Offer 决定（未决定显示「待决定」），其余显示最新轮次结果 */
function resultDisplay(row: ListRow): { label: string; color: string } | null {
  if (row.status === 'offer') {
    return row.offerDecision
      ? { label: RESULT_LABELS[row.offerDecision], color: RESULT_COLORS[row.offerDecision] }
      : { label: '待决定', color: '#94A3B8' }
  }
  return row.latestResult
    ? { label: RESULT_LABELS[row.latestResult], color: RESULT_COLORS[row.latestResult] }
    : null
}

/** 结果下拉选项随状态切换（Offer 态仅接受 / 拒绝） */
function resultOptions(row: ListRow): RoundResult[] {
  return row.status === 'offer' ? OFFER_RESULT_OPTIONS : NORMAL_RESULT_OPTIONS
}

async function quickSetResult(row: ListRow, r: RoundResult) {
  if (row.status === 'offer') {
    if (r !== 'accepted' && r !== 'rejected_offer') return
    await store.setOfferDecision(row.id, r)
  } else {
    const latest = latestRound(row)
    if (latest) await store.updateRound(latest.id, { result: r })
  }
}

/** Base 多选勾选即保存（静默，不弹 toast） */
async function saveBase(row: ListRow) {
  await store.update(row.id, { base: row.base }, true)
}

function openCreate() {
  editing.value = null
  formVisible.value = true
}

function openEdit(row: Application) {
  editing.value = row
  formVisible.value = true
}

function goDetail(row: Application) {
  void view.navigate(`/jobs/applications/${row.id}`)
}

async function confirmRemove(row: Application) {
  const title = row.position ? `${row.company} - ${row.position}` : row.company
  const ok = await ElMessageBox.confirm(
    `确定删除「${title}」吗？其下所有流程轮次也会一并删除。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (ok) await store.remove(row.id)
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.table-card :deep(.el-card__body) {
  padding: 0;
}

/* 固定 10 行容量：最后一页不满时表格撑高留白，分页条位置恒定 */
.table-card :deep(.el-table) {
  min-height: 450px;
}

.table-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 14px 16px 12px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  padding: 14px 16px;
  border-top: 1px solid var(--line-soft);
}

.company {
  font-weight: 600;
}

.channel-link {
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

.status-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.result-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.base-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: #374151;
}

.base-trigger .base-empty {
  color: #9ca3af;
}

.base-options {
  display: flex;
  flex-wrap: wrap;
  column-gap: 4px;
}

.base-add {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.caret {
  color: #909399;
  font-size: 12px;
}

.result-tag {
  border: none;
  color: #fff;
  font-weight: 600;
  border-radius: 999px;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
