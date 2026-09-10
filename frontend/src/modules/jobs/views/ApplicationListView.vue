<template>
  <div class="page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索公司 / 岗位"
        clearable
        prefix-icon="Search"
        style="width: 220px"
      />
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 140px">
        <el-option v-for="s in STATUS_ORDER" :key="s" :label="STATUS_LABELS[s]" :value="s" />
      </el-select>
      <el-select
        v-model="filterChannel"
        placeholder="渠道"
        clearable
        style="width: 140px"
      >
        <el-option v-for="c in channelOptions" :key="c" :label="c" :value="c" />
      </el-select>
      <div class="spacer" />
      <el-button type="primary" icon="Plus" @click="openCreate">新增投递</el-button>
    </div>

    <!-- 列表 -->
    <el-table
      v-loading="store.loading"
      :data="rows"
      row-key="id"
      :default-sort="{ prop: 'applyDate', order: 'descending' }"
      @row-click="goDetail"
    >
      <el-table-column prop="company" label="公司" min-width="140" sortable>
        <template #default="{ row }">
          <span class="company">{{ row.company }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="position" label="岗位" min-width="150" sortable>
        <template #default="{ row }">{{ row.position ?? '—' }}</template>
      </el-table-column>
      <el-table-column prop="channel" label="渠道" width="110">
        <template #default="{ row }">{{ row.channel ?? '—' }}</template>
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
      <el-table-column prop="applyDate" label="投递日期" width="120" sortable>
        <template #default="{ row }">{{ row.applyDate ?? '—' }}</template>
      </el-table-column>
      <el-table-column prop="deadline" label="截止时间" width="125" sortable :sort-method="sortByDeadline">
        <template #default="{ row }">
          {{ row.deadline ? dayjs(row.deadline).format('MM-DD HH:mm') : '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="salary" label="薪资" width="120">
        <template #default="{ row }">{{ row.salary ?? '—' }}</template>
      </el-table-column>
      <el-table-column prop="location" label="地点" width="100">
        <template #default="{ row }">{{ row.location ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="160">
        <template #default="{ row }">
          <el-dropdown trigger="click" @command="(s: ApplicationStatus) => store.quickSetStatus(row.id, s)">
            <span class="status-trigger" @click.stop>
              <StatusTag :status="row.status" :reject-stage="row.rejectStage" />
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

    <ApplicationFormDialog
      v-model="formVisible"
      :application="editing"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import StatusTag from '../components/StatusTag.vue'
import ApplicationFormDialog from '../components/ApplicationFormDialog.vue'
import { STATUS_LABELS, STATUS_ORDER, CHANNELS } from '../constants'
import { useJobsStore } from '../store'
import type { Application, ApplicationStatus } from '../types'

const router = useRouter()
const store = useJobsStore()

const keyword = ref('')
const filterStatus = ref<ApplicationStatus | ''>('')
const filterChannel = ref<string>('')

const formVisible = ref(false)
const editing = ref<Application | null>(null)

onMounted(() => store.ensureLoaded())

const channelOptions = computed(() => [
  // 固定渠道 + 数据中出现过的其他渠道（兼容旧数据），去重
  ...new Set([...CHANNELS, ...store.applications.map((a) => a.channel).filter((c): c is string => !!c)]),
])

/** 筛选 + 搜索（数据量小，全部前端现算） */
const filtered = computed(() => {
  let rows = store.applications
  if (keyword.value) {
    const k = keyword.value.toLowerCase()
    rows = rows.filter(
      (a) =>
        a.company.toLowerCase().includes(k) || a.position.toLowerCase().includes(k),
    )
  }
  if (filterStatus.value) rows = rows.filter((a) => a.status === filterStatus.value)
  if (filterChannel.value) rows = rows.filter((a) => a.channel === filterChannel.value)
  return rows
})

/** 截止时间 = 流程轮次中最新的计划时间 */
function latestRoundTime(a: Application): string | null {
  const times = a.rounds.map((r) => r.scheduledAt).filter((t): t is string => !!t)
  return times.length ? times.reduce((m, t) => (t > m ? t : m)) : null
}

/** 列表行 = 筛选结果 + 现算的截止时间 */
const rows = computed(() => filtered.value.map((a) => ({ ...a, deadline: latestRoundTime(a) })))

/** 截止时间排序：空值永远排最后 */
function sortByDeadline(
  a: Application & { deadline: string | null },
  b: Application & { deadline: string | null },
) {
  return (a.deadline ?? '9999').localeCompare(b.deadline ?? '9999')
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
  router.push(`/jobs/applications/${row.id}`)
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
  gap: 16px;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.spacer {
  flex: 1;
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

.caret {
  color: #909399;
  font-size: 12px;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>