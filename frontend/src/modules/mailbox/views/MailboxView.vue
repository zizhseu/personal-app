<template>
  <div class="mailbox-page">
    <div class="page-heading">
      <div><h1>邮件同步</h1><p>将新增招聘邮件关联到岗位，保留每次判断及更新依据。</p></div>
      <div class="toolbar">
        <el-button @click="load(false)">刷新</el-button>
        <el-button type="primary" :loading="starting || account?.scanning" :disabled="!account" @click="scan">{{ account?.scanning ? '正在扫描与整理' : '手动扫描' }}</el-button>
      </div>
    </div>
    <el-alert v-if="loadFailed" title="邮件记录读取失败，请点击刷新重试" type="error" :closable="false" />
    <el-alert v-if="!account && loaded" title="先连接 163 邮箱，建立新邮件基线" type="info" :closable="false">
      <template #default><RouterLink to="/settings">前往设置连接邮箱</RouterLink></template>
    </el-alert>
    <el-card v-if="account" shadow="never" class="account-card">
      <div class="account-row">
        <div><strong>{{ account.address }}</strong><el-tag size="small" :type="account.enabled ? 'success' : 'info'">{{ account.enabled ? '每小时定时扫描' : '手动扫描模式' }}</el-tag></div>
        <RouterLink to="/settings">邮箱设置</RouterLink>
      </div>
      <p>上次扫描 {{ formatDateTime(account.lastScanAt) }} <span v-if="account.enabled"> · 下次定时 {{ formatDateTime(account.nextScanAt) }}</span></p>
      <p class="note">从 {{ formatDateTime(account.baselineAt) }} 建立基线。明确匹配的事件自动更新，重复提醒和投递推荐保留判断记录。</p>
      <el-alert v-if="account.lastError" :title="account.lastError" type="warning" :closable="false" />
    </el-card>
    <div class="summary">
      <div><span>已更新</span><strong>{{ counts.applied || 0 }}</strong></div>
      <div><span>待核对</span><strong>{{ counts.review || 0 }}</strong></div>
      <div><span>重复邮件</span><strong>{{ counts.duplicate || 0 }}</strong></div>
      <div><span>处理失败</span><strong>{{ counts.failed || 0 }}</strong></div>
    </div>
    <el-card shadow="never" class="records">
      <div class="filter-row"><h2>处理记录</h2><el-select v-model="view.state.status" aria-label="邮件处理状态" style="width: 160px"><el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" /></el-select></div>
      <el-table v-loading="loading" :data="items" empty-text="暂无新增邮件处理记录" @row-click="openMessage">
        <el-table-column label="邮件" min-width="280"><template #default="{ row }"><div class="mail-title">{{ row.subject }}</div><div class="muted">{{ row.sender }}</div></template></el-table-column>
        <el-table-column label="收到时间" width="160"><template #default="{ row }">{{ formatDateTime(row.receivedAt) }}</template></el-table-column>
        <el-table-column label="处理状态" width="110"><template #default="{ row }"><el-tag :type="tagType(row.status)">{{ statusLabels[row.status] || row.status }}</el-tag></template></el-table-column>
        <el-table-column label="判断依据与变更" min-width="240" show-overflow-tooltip><template #default="{ row }">{{ row.changeSummary || row.reason || '等待处理' }}</template></el-table-column>
        <el-table-column width="85"><template #default="{ row }"><el-button text type="primary" @click.stop="openMessage(row)">查看</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-if="total > 30" v-model:current-page="view.state.page" :page-size="30" :total="total" layout="prev, pager, next, total" class="pagination" />
    </el-card>

    <el-dialog v-model="detailVisible" title="邮件处理详情" width="min(860px, calc(100vw - 32px))" class="mail-detail" destroy-on-close>
      <div v-if="detail" class="detail-content">
        <h3>{{ detail.subject }}</h3><p class="muted">{{ detail.sender }} · {{ formatDateTime(detail.sentAt || detail.receivedAt) }}</p>
        <el-alert :title="detail.changeSummary || detail.reason || statusLabels[detail.status] || '等待处理'" :type="detail.status === 'failed' ? 'error' : detail.status === 'review' ? 'warning' : 'info'" :closable="false" />
        <template v-if="detail.proposal">
          <div class="proposal-grid">
            <div><span>公司（邮件原文）</span><strong>{{ detail.proposal.company || '待关联' }}</strong></div>
            <div v-if="detail.proposal.matchedCompany"><span>公司（系统匹配）</span><strong>{{ detail.proposal.matchedCompany }}</strong></div>
            <div><span>岗位</span><strong>{{ detail.proposal.position || '未明确' }}</strong></div>
            <div><span>轮次</span><strong>{{ detail.proposal.roundType ? ROUND_TYPE_LABELS[detail.proposal.roundType] : '未明确' }}</strong></div>
            <div><span>结果</span><strong>{{ detail.proposal.result ? RESULT_LABELS[detail.proposal.result] : '未提及' }}</strong></div>
            <div><span>开始时间</span><strong>{{ formatDateTime(detail.proposal.startAt) }}</strong></div>
            <div><span>截止时间</span><strong>{{ formatDateTime(detail.proposal.deadlineAt) }}</strong></div>
          </div>
          <p v-if="detail.proposal.companyMatchReason" class="muted">公司匹配依据 {{ detail.proposal.companyMatchReason }}</p>
          <p v-if="detail.proposal.positionMatchReason" class="muted">岗位归属依据 {{ detail.proposal.positionMatchReason }}</p>
          <blockquote>{{ detail.proposal.evidence }}</blockquote>
          <el-collapse v-if="detail.proposal.companySearchResults?.length">
            <el-collapse-item title="公司关键词与检索候选" name="company-search">
              <div v-for="search in detail.proposal.companySearchResults" :key="search.keyword" class="search-result">
                <strong>{{ search.keyword }}</strong><el-tag v-if="search.hasMore" type="info" size="small">结果已限量</el-tag>
                <p>{{ search.companies.join('、') || '暂无候选' }}</p>
              </div>
            </el-collapse-item>
          </el-collapse>
        </template>
        <div v-if="canApply" class="association">
          <h4>核对并关联岗位</h4>
          <el-button text type="primary" @click="refreshTargets">刷新岗位信息</el-button>
          <el-radio-group v-model="creatingPosition" aria-label="邮件岗位处理方式">
            <el-radio-button :value="false">更新已有岗位</el-radio-button>
            <el-radio-button v-if="!requiresRound" :value="true">在公司下新增岗位</el-radio-button>
          </el-radio-group>
          <template v-if="creatingPosition">
            <el-select v-model="companyIndex" filterable placeholder="选择已投递公司" aria-label="新岗位所属公司">
              <el-option v-for="(company, index) in companies" :key="company.applicationId" :value="index" :label="`${company.company} · ${company.currentPosition || '暂无当前岗位'}`" />
            </el-select>
            <el-input v-model="newPosition" maxlength="100" placeholder="新岗位或招聘单位名称" aria-label="邮件新岗位名称" />
            <p class="muted">新岗位作为该公司下的独立流程保存。</p>
          </template>
          <el-select v-else v-model="targetIndex" filterable placeholder="选择公司及具体岗位流程" aria-label="邮件关联岗位" @change="roundId = 0">
            <el-option v-for="(target, index) in targets" :key="index" :value="index" :label="`${target.company} / ${target.position || '未填写岗位'} · 岗位记录 ${target.displayOrder} · ${STATUS_LABELS[target.status] || '状态未知'}`" />
          </el-select>
          <el-select v-if="!creatingPosition && selectedTarget" v-model="roundId" placeholder="选择对应轮次" aria-label="邮件关联轮次">
            <el-option v-if="!requiresRound" :value="0" label="新增轮次" />
            <el-option v-for="round in eligibleRounds" :key="round.id" :value="round.id" :label="`${ROUND_TYPE_LABELS[round.roundType]} #${round.id} · ${formatDateTime(round.startAt)} · ${RESULT_LABELS[round.result]}`" />
          </el-select>
          <p class="muted">请对照原文核对时间与轮次，确认后提交上方事件。重复邀请可直接忽略。</p>
          <el-button type="primary" :loading="acting" :disabled="creatingPosition ? !selectedCompany || !newPosition.trim() : !selectedTarget || (requiresRound && !roundId)" @click="apply">{{ creatingPosition ? '确认新增岗位并更新流程' : '确认更新此岗位' }}</el-button>
        </div>
        <p v-if="detail.changes && detail.changes.before.status !== detail.changes.after.status">岗位阶段 {{ STATUS_LABELS[detail.changes.before.status] || detail.changes.before.status }} → {{ STATUS_LABELS[detail.changes.after.status] || detail.changes.after.status }}</p>
        <p v-if="detail.applicationId"><RouterLink :to="{ path: `/jobs/applications/${detail.applicationId}`, query: detail.changes?.after.round?.positionVersion ? { positionVersion: String(detail.changes.after.round.positionVersion) } : {} }" @click="detailVisible = false">查看本次更新的岗位流程</RouterLink></p>
        <p v-if="detail.duplicateOf" class="muted">与处理记录 #{{ detail.duplicateOf }} 重复</p>
        <el-collapse><el-collapse-item title="原始邮件正文" name="body"><pre>{{ detail.body || '正文为空，请在邮箱中核对原邮件' }}</pre></el-collapse-item></el-collapse>
        <p v-if="detail.attachments.length" class="muted">附件 {{ detail.attachments.join('、') }}，请在邮箱中查看附件内容。</p>
      </div>
      <template #footer>
        <div class="dialog-actions">
          <el-button v-if="detail && ['review', 'failed'].includes(detail.status)" :disabled="acting" @click="ignore">忽略此邮件</el-button>
          <el-button v-if="detail && !['applied', 'unchanged', 'pending', 'analyzing'].includes(detail.status)" :disabled="account?.scanning" :loading="acting" @click="retry">重新分析</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ROUND_TYPE_LABELS, RESULT_LABELS, STATUS_LABELS } from '@/modules/jobs/constants'
import { formatDateTime } from '@/shared/utils/format'
import { useJobsStore } from '@/modules/jobs/store'
import { useListViewState } from '@/shared/composables/useListViewState'
import { choiceField, pageField } from '@/shared/state/pageState'
import * as api from '../api'
import type { MailAccount, MailCompanyTarget, MailMessage, MailTarget } from '../types'

const statusLabels: Record<string, string> = { all: '全部状态', pending: '待处理', analyzing: '整理中', applied: '已更新', unchanged: '已核对', review: '待核对', duplicate: '重复邮件', ignored: '已忽略', failed: '处理失败' }
const jobs = useJobsStore()
const account = ref<MailAccount | null>(null), items = ref<MailMessage[]>([])
const counts = ref<Record<string, number>>({}), total = ref(0)
const loading = ref(false), loaded = ref(false), loadFailed = ref(false), starting = ref(false), acting = ref(false)
const detailVisible = ref(false), detail = ref<MailMessage | null>(null), targets = ref<MailTarget[]>([])
const targetIndex = ref<number | null>(null), roundId = ref(0)
const companies = ref<MailCompanyTarget[]>([]), companyIndex = ref<number | null>(null)
const creatingPosition = ref(false), newPosition = ref('')
const view = useListViewState({ status: choiceField('all', Object.keys(statusLabels)), page: pageField() }, {
  routes: ['aitools-mailbox'], ready: () => loaded.value && !loading.value, count: () => total.value, pageSize: 30,
})
const selectedTarget = computed(() => targetIndex.value === null ? null : targets.value[targetIndex.value])
const selectedCompany = computed(() => companyIndex.value === null ? null : companies.value[companyIndex.value])
const eligibleRounds = computed(() => selectedTarget.value?.rounds.filter(round => round.roundType === detail.value?.proposal?.roundType) ?? [])
const requiresRound = computed(() => ['result', 'reschedule'].includes(detail.value?.proposal?.eventType || ''))
const canApply = computed(() => detail.value?.status === 'review' && detail.value.proposal?.category === 'event' && detail.value.proposal.eventType !== 'application_received')
let timer: ReturnType<typeof setInterval> | undefined
let requestVersion = 0

function tagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  return status === 'applied' ? 'success' : status === 'review' ? 'warning' : status === 'failed' ? 'danger' : 'info'
}
async function load(silent = false) {
  const version = ++requestVersion
  if (!silent) loading.value = true
  try {
    const [status, messages] = await Promise.all([api.getMailStatus(silent), api.getMessages(view.state.status, view.state.page, silent)])
    if (version !== requestVersion) return
    account.value = status.account
    items.value = messages.items; total.value = messages.total; counts.value = messages.counts
    loaded.value = true; loadFailed.value = false
  } catch { if (version === requestVersion) loadFailed.value = true }
  finally { if (version === requestVersion) loading.value = false }
}
async function scan() {
  starting.value = true
  try { await api.scanMailbox(); ElMessage.success('扫描已开始，处理结果会自动刷新'); await load(true) }
  catch { /* 请求错误由统一入口显示。 */ }
  finally { starting.value = false }
}
async function openMessage(message: MailMessage) {
  try {
    const [row, choices, parents] = await Promise.all([api.getMessage(message.id), api.getTargets(), api.getCompanyTargets()])
    detail.value = row; targets.value = choices; companies.value = parents; targetIndex.value = null; roundId.value = 0
    companyIndex.value = null
    creatingPosition.value = row.proposal?.positionAction === 'create'
    newPosition.value = row.proposal?.targetPosition || row.proposal?.position || row.proposal?.company || ''
    const candidates = parents.map((parent, index) => ({ parent, index })).filter(({ parent }) => parent.company === row.proposal?.matchedCompany)
    if (candidates.length === 1) companyIndex.value = candidates[0]!.index
    detailVisible.value = true
  } catch { /* 请求错误由统一入口显示。 */ }
}
async function apply() {
  if (!detail.value) return
  if (creatingPosition.value ? !selectedCompany.value : !selectedTarget.value) return
  acting.value = true
  try {
    detail.value = creatingPosition.value
      ? await api.applyNewPosition(detail.value.id, selectedCompany.value!, newPosition.value.trim())
      : await api.applyMessage(detail.value.id, selectedTarget.value!, roundId.value || undefined)
    if (detail.value.status === 'applied') ElMessage.success(detail.value.changeSummary || '已更新所选岗位')
    else ElMessage.info(detail.value.changeSummary || detail.value.reason || '已核对现有记录')
    await jobs.loadAll()
    await load(true)
  }
  catch { /* 保留详情，供重新核对。 */ }
  finally { acting.value = false }
}
async function refreshTargets() {
  try {
    const [choices, parents] = await Promise.all([api.getTargets(), api.getCompanyTargets()])
    targets.value = choices; companies.value = parents; targetIndex.value = null; companyIndex.value = null; roundId.value = 0
  }
  catch { /* 请求错误由统一入口显示。 */ }
}
async function ignore() {
  if (!detail.value) return
  acting.value = true
  try { detail.value = await api.ignoreMessage(detail.value.id); await load(true) }
  catch { /* 请求错误由统一入口显示。 */ }
  finally { acting.value = false }
}
async function retry() {
  if (!detail.value) return
  acting.value = true
  try { await api.retryMessage(detail.value.id); detailVisible.value = false; ElMessage.success('已开始重新分析'); await load(true) }
  catch { /* 请求错误由统一入口显示。 */ }
  finally { acting.value = false }
}
watch(() => [view.state.status, view.state.page], () => { void load() })
onMounted(() => { void load(); timer = setInterval(() => { if (!document.hidden) void load(true) }, 5000) })
onBeforeUnmount(() => { requestVersion++; clearInterval(timer) })
</script>

<style scoped>
.mailbox-page { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.page-heading, .account-row, .filter-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
h1 { margin: 0; font-size: 22px; color: var(--ink); }
h2 { margin: 0; font-size: 16px; }
h3 { margin: 0 0 8px; overflow-wrap: anywhere; }
p { color: var(--ink-3); font-size: 13px; line-height: 1.7; margin: 7px 0; }
.toolbar { display: flex; }
.account-card, .records { border-radius: var(--radius-card); }
.account-row strong { margin-right: 16px; }
a { color: var(--el-color-primary); font-size: 13px; }
.note, .muted { color: var(--ink-3); font-size: 12px; }
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.summary > div { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: var(--radius-card); }
.summary span { color: var(--ink-3); font-size: 13px; }
.summary strong { font-size: 25px; color: var(--ink); }
.filter-row { margin-bottom: 18px; }
.mail-title { font-weight: 600; color: var(--ink); }
.pagination { margin-top: 18px; justify-content: flex-end; }
.detail-content { max-height: 65vh; overflow-y: auto; padding-right: 8px; }
.proposal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0; }
.proposal-grid span { display: block; color: var(--ink-3); font-size: 12px; margin-bottom: 5px; }
.proposal-grid strong { font-size: 14px; font-weight: 500; }
blockquote { margin: 16px 0; padding: 12px 16px; background: var(--el-fill-color-light); border-left: 3px solid var(--el-color-primary); white-space: pre-wrap; overflow-wrap: anywhere; }
.association { display: flex; flex-direction: column; gap: 12px; margin: 18px 0; padding: 18px; border: 1px solid var(--el-border-color); border-radius: 10px; }
.association h4 { margin: 0; }
.search-result { margin: 10px 0; overflow-wrap: anywhere; }
.search-result .el-tag { margin-left: 10px; }
.association .el-button { align-self: flex-start; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; font-size: 13px; line-height: 1.8; }
.dialog-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
@media (max-width: 700px) { .page-heading, .account-row { align-items: flex-start; flex-direction: column; } .summary { grid-template-columns: 1fr 1fr; gap: 10px; } .summary > div { padding: 14px; } .proposal-grid { grid-template-columns: 1fr; } }
</style>
