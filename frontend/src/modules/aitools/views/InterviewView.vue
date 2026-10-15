<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>AI 面试</h1>
        <p class="sub">围绕简历中的项目与经历提问，根据回答逐步深入</p>
      </div>
      <div class="actions">
        <el-button v-if="activeId" icon="Plus" @click="newInterview">新建面试</el-button>
        <el-button icon="Refresh" @click="refreshCurrent">刷新记录</el-button>
      </div>
    </div>
    <el-alert v-if="demoMode" type="info" :closable="false" show-icon title="当前使用模拟回复演示流程，生成内容不代表真实模型效果" />
    <el-alert v-if="!llmReady && !statusLoading" type="warning" :closable="false" show-icon title="尚未配置模型服务" description="请在 backend/.env 中配置 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL 后重启后端。简历与历史记录仍可正常查看和管理。" />

    <div class="interview-grid">
      <section class="workspace" aria-label="面试工作区">
        <el-card v-if="!activeId" shadow="never" class="setup-card">
          <template #header><span class="section-title">准备一次简历面试</span></template>
          <el-form label-position="top" @submit.prevent="startInterview">
            <el-form-item label="面试使用的简历">
              <div class="resume-picker">
                <el-select v-model="resumeId" placeholder="选择一份已保存的简历" :loading="resumesLoading" :disabled="creating">
                  <el-option v-for="resume in resumes" :key="resume.id" :value="resume.id" :label="resume.name" />
                </el-select>
                <el-button icon="Plus" :disabled="creating" @click="openResumeEditor(null)">新增简历</el-button>
                <el-button v-if="resumeId" icon="EditPen" :disabled="creating" @click="openResumeEditor(resumeId)">编辑</el-button>
                <el-button v-if="resumeId" type="danger" plain :disabled="creating" @click="removeResume">删除</el-button>
              </div>
            </el-form-item>
            <el-empty v-if="!resumes.length && !resumesLoading" description="先添加简历，面试官会从你的实际经历开始提问" :image-size="70" />
            <el-collapse v-if="selectedResume" class="material-preview">
              <el-collapse-item title="查看简历内容" name="resume"><pre class="resume-text">{{ selectedResume.content }}</pre></el-collapse-item>
            </el-collapse>
            <div class="setup-fields">
              <el-form-item label="目标岗位（选填）"><el-input v-model="targetRole" placeholder="例如：AI 应用开发" maxlength="100" :disabled="creating" /></el-form-item>
              <el-form-item label="重点考察方向（选填）"><el-input v-model="focus" placeholder="例如：项目实现、个人贡献、技术选择与验证过程" maxlength="500" :disabled="creating" /></el-form-item>
            </div>
            <div class="setup-guide">
              <span class="guide-icon"><el-icon><Document /></el-icon></span>
              <div><strong>从经历出发，逐步追问</strong><p>面试会保存这份简历的快照与每一轮对话。结束后查看逐题复盘，再选择要加入问答或待办的内容。</p></div>
            </div>
            <el-button type="primary" size="large" icon="VideoPlay" :loading="creating" :disabled="!resumeId || !llmReady || statusLoading" @click="startInterview">开始面试</el-button>
          </el-form>
        </el-card>

        <template v-else-if="session">
          <el-card shadow="never" class="session-header">
            <div class="session-heading">
              <div><h2>{{ session.resumeName }}</h2><p>{{ session.targetRole || '简历项目与经历面试' }} · {{ dateText(session.createdAt) }} · 已作答 {{ answerCount }} 次</p></div>
              <el-tag :type="session.status === 'completed' ? 'success' : 'primary'" effect="plain">{{ session.status === 'completed' ? '已复盘' : '进行中' }}</el-tag>
            </div>
            <el-collapse class="snapshot"><el-collapse-item title="查看本场简历快照" name="source"><pre class="resume-text">{{ session.resumeContent }}</pre><p v-if="session.focus" class="hint">重点考察：{{ session.focus }}</p></el-collapse-item></el-collapse>
          </el-card>
          <el-tabs v-model="sessionTab" class="session-tabs">
            <el-tab-pane label="面试对话" name="dialogue" />
            <el-tab-pane v-if="session.report" label="复盘报告" name="report" />
          </el-tabs>
          <InterviewReport v-if="sessionTab === 'report' && session.report" :session="session" @changed="reloadExported" />
          <template v-else>
            <el-alert v-if="failedOperation" type="error" :closable="false" show-icon :title="failedOperation.error || '上次生成未完成'">
              <template #default><div class="recovery"><span>{{ session.messages.some(message => message.role === 'user') ? '你的回答已保存，可以重试。' : '简历与面试记录已保存，可以重新生成问题。' }}</span><el-button size="small" :disabled="working || !llmReady" @click="retryGeneration">{{ failedOperation.kind === 'review' ? '重试生成复盘' : '重试生成' }}</el-button></div></template>
            </el-alert>
            <el-card shadow="never" class="chat-card">
              <div ref="chatScroll" class="chat-scroll" aria-label="面试对话记录" aria-live="polite">
                <div v-for="message in session.messages" :key="message.id" class="message" :class="message.role">
                  <span class="speaker">{{ message.role === 'assistant' ? '面试官' : '我' }}</span>
                  <div v-if="message.role === 'assistant'" class="bubble md-body" v-html="renderMarkdown(message.content)" />
                  <div v-else class="bubble user-bubble">{{ message.content }}</div>
                </div>
                <div v-if="working" class="thinking"><span class="thinking-dot" />{{ generationKind === 'review' ? '正在整理本场复盘…' : '面试官正在思考…' }}<span>可以离开页面，稍后从历史记录继续查看。</span></div>
                <el-empty v-if="!session.messages.length && !working" description="材料已保存，生成第一个面试问题后开始作答" :image-size="70">
                  <el-button v-if="!failedOperation" type="primary" :disabled="!llmReady" @click="perform(session.id, 'start')">生成第一个问题</el-button>
                </el-empty>
              </div>
            </el-card>
            <template v-if="session.status === 'active'">
              <div class="input-bar">
                <el-input v-model="input" type="textarea" :rows="3" maxlength="6000" show-word-limit resize="none" :disabled="!canSend" :placeholder="listening ? '请对着麦克风回答…' : '输入你的回答。Ctrl + Enter 发送，Enter 换行。'" @keydown.ctrl.enter.prevent="sendAnswer" />
                <el-button type="primary" :disabled="!canSend || !input.trim()" @click="sendAnswer">发送回答</el-button>
              </div>
              <div class="interview-actions">
                <div class="voice-actions"><el-button :icon="muted ? 'Mute' : 'Bell'" @click="toggleVoice">{{ muted ? '开启语音' : '关闭语音' }}</el-button><el-button v-if="hasSpeechRecognition" :type="listening ? 'danger' : 'default'" icon="Microphone" :disabled="!canSend" @click="toggleMic">{{ listening ? '停止识别' : '语音输入' }}</el-button></div>
                <el-button type="primary" plain icon="DocumentChecked" :disabled="working || answerCount === 0 || !llmReady" @click="finishInterview">结束并生成复盘</el-button>
              </div>
              <p class="hint">回答提交后自动保存。语音输入与播放需要浏览器和网络支持。</p>
            </template>
            <el-button v-else type="primary" plain @click="sessionTab = 'report'">查看复盘报告</el-button>
          </template>
        </template>
        <el-card v-else shadow="never"><el-skeleton v-if="sessionLoading" :rows="7" animated /><el-empty v-else description="面试记录暂时无法读取，请刷新重试"><el-button @click="refreshCurrent">重新加载</el-button></el-empty></el-card>
      </section>

      <el-card shadow="never" class="history-card">
        <template #header><div class="history-heading"><span class="section-title">面试记录</span><span class="history-count">{{ history.length }} 场</span></div></template>
        <div v-loading="historyLoading" class="history-list">
          <div v-for="record in history" :key="record.id" class="history-row" :class="{ active: activeId === record.id }">
            <button type="button" class="history-link" @click="openInterview(record.id)"><span class="history-title">{{ record.resumeName }}</span><span class="history-role">{{ record.targetRole || '简历面试' }}</span><span class="history-meta"><span :class="{ completed: record.status === 'completed' }">{{ record.status === 'completed' ? '已复盘' : '进行中' }}</span>{{ dateText(record.createdAt) }}</span></button>
            <button type="button" class="history-delete" :aria-label="`删除面试记录 ${record.resumeName}`" title="删除记录" :disabled="busyKinds.has(record.id)" @click="removeInterview(record)"><el-icon><Delete /></el-icon></button>
          </div>
          <el-empty v-if="!history.length && !historyLoading" description="面试开始后，记录会保存在这里" :image-size="55" />
        </div>
      </el-card>
    </div>
    <ResumeEditor v-model="resumeEditorOpen" :resume-id="editingResumeId" @saved="resumeSaved" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { renderMarkdown } from '@/shared/utils/markdown'
import * as api from '../api'
import type { InterviewOperation, InterviewSession, InterviewSummary, ResumeDocument, ResumeSummary } from '../types'
import { useInterviewAudio } from '../useInterviewAudio'
import ResumeEditor from '../components/ResumeEditor.vue'
import InterviewReport from '../components/InterviewReport.vue'

const route = useRoute()
const router = useRouter()
const activeId = computed(() => { const value = Number(route.query.session); return Number.isSafeInteger(value) && value > 0 ? value : null })
const resumes = ref<ResumeSummary[]>([])
const history = ref<InterviewSummary[]>([])
const resumeId = ref<number | null>(null)
const selectedResume = ref<ResumeDocument | null>(null)
const session = ref<InterviewSession | null>(null)
const resumeEditorOpen = ref(false)
const editingResumeId = ref<number | null>(null)
const targetRole = ref('')
const focus = ref('')
const input = ref('')
const llmReady = ref(false)
const statusLoading = ref(true)
const demoMode = ref(false)
const resumesLoading = ref(false)
const historyLoading = ref(false)
const sessionLoading = ref(false)
const creating = ref(false)
const busyKinds = ref(new Map<number, InterviewOperation['kind']>())
const sessionTab = ref('dialogue')
const chatScroll = ref<HTMLElement>()
const { muted, listening, hasSpeechRecognition, speak, stopAll, stopRecognition, toggleMic, toggleVoice } = useInterviewAudio(input)
let disposed = false
let loadVersion = 0
let resumeVersion = 0
let pollTimer: ReturnType<typeof setTimeout> | undefined
let pollFailures = 0

const working = computed(() => !!activeId.value && (busyKinds.value.has(activeId.value) || session.value?.lastOperation?.status === 'pending'))
const generationKind = computed(() => (activeId.value ? busyKinds.value.get(activeId.value) : null) ?? session.value?.lastOperation?.kind)
const failedOperation = computed(() => session.value?.lastOperation?.status === 'failed' ? session.value.lastOperation : null)
const answerCount = computed(() => session.value?.messages.filter(message => message.role === 'user').length ?? 0)
const canSend = computed(() => !!session.value && session.value.status === 'active' && !working.value && llmReady.value && session.value.messages.at(-1)?.role === 'assistant')
const dateText = (value: string) => dayjs(value).format('MM-DD HH:mm')

async function loadResumes() {
  resumesLoading.value = true
  try { resumes.value = await api.fetchResumes(); if (!resumes.value.some(row => row.id === resumeId.value)) resumeId.value = resumes.value[0]?.id ?? null }
  catch { /* 请求拦截器提示失败，保留已有列表。 */ }
  finally { resumesLoading.value = false }
}
async function loadHistory() {
  historyLoading.value = true
  try { history.value = await api.fetchInterviews() } catch { /* 保留当前记录。 */ }
  finally { historyLoading.value = false }
}
function applySession(value: InterviewSession) {
  if (disposed || activeId.value !== value.id) return
  if (session.value?.id === value.id && session.value.updatedAt > value.updatedAt) return
  if (value.report && !session.value?.report) sessionTab.value = 'report'
  session.value = value
  void nextTick(() => { if (chatScroll.value) chatScroll.value.scrollTop = chatScroll.value.scrollHeight })
}
async function loadSession(id: number) {
  if (disposed || activeId.value !== id) return
  const version = ++loadVersion
  const value = await api.fetchInterview(id)
  if (version === loadVersion) applySession(value)
}
function schedulePoll() {
  clearTimeout(pollTimer)
  if (disposed || session.value?.lastOperation?.status !== 'pending' || pollFailures >= 3) return
  const id = session.value.id
  pollTimer = setTimeout(async () => {
    try { await loadSession(id); pollFailures = 0 } catch { pollFailures++ }
    schedulePoll()
  }, 1600)
}
watch(() => [session.value?.id, session.value?.lastOperation?.status], schedulePoll)
watch(activeId, async (id) => {
  ++loadVersion
  stopAll(); input.value = ''; session.value = null; sessionTab.value = 'dialogue'; pollFailures = 0
  clearTimeout(pollTimer)
  sessionLoading.value = !!id
  if (!id) return
  try { await loadSession(id) } catch { /* 显示可重新加载的空态。 */ }
  finally { if (activeId.value === id) sessionLoading.value = false }
}, { immediate: true })
watch(resumeId, async (id) => {
  const version = ++resumeVersion
  selectedResume.value = null
  if (!id) return
  try { const value = await api.fetchResume(id); if (version === resumeVersion) selectedResume.value = value } catch { /* 可以重新选择或编辑。 */ }
})

onMounted(async () => {
  await Promise.all([loadResumes(), loadHistory()])
  try { const status = await api.fetchStatus(); llmReady.value = status.llmReady; demoMode.value = !!status.demoMode }
  catch { llmReady.value = false }
  finally { statusLoading.value = false }
})
onBeforeUnmount(() => { disposed = true; ++loadVersion; clearTimeout(pollTimer) })

function openResumeEditor(id: number | null) { editingResumeId.value = id; resumeEditorOpen.value = true }
async function resumeSaved(value: ResumeDocument) { await loadResumes(); resumeId.value = value.id; selectedResume.value = value }
async function removeResume() {
  if (!resumeId.value) return
  const id = resumeId.value
  const ok = await ElMessageBox.confirm('删除这份简历？已开始的面试仍保留当时的简历快照。', '删除简历', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }).catch(() => false)
  if (!ok) return
  try { await api.deleteResume(id); await loadResumes(); ElMessage.success('简历已删除') } catch { /* 请求拦截器已提示。 */ }
}
async function newInterview() { await router.push({ path: '/aitools/interview' }) }
async function openInterview(id: number) { await router.push({ path: '/aitools/interview', query: { session: id } }) }
async function startInterview() {
  if (!resumeId.value || !llmReady.value || creating.value) return
  creating.value = true
  try {
    const value = await api.createInterview({ resumeId: resumeId.value, targetRole: targetRole.value, focus: focus.value })
    await openInterview(value.id)
    applySession(value)
    await perform(value.id, 'start')
  } catch { /* 已保存的面试可以从记录中重新打开。 */ }
  finally { creating.value = false; await loadHistory() }
}
async function perform(id: number, action: 'start' | 'messages' | 'review' | 'retry', content?: string) {
  if (busyKinds.value.has(id)) return
  const requestId = action === 'retry' ? session.value?.lastOperation?.id : crypto.randomUUID()
  if (!requestId) return
  const kind = action === 'messages' ? 'reply' : action === 'retry' ? session.value?.lastOperation?.kind ?? 'start' : action
  busyKinds.value = new Map(busyKinds.value).set(id, kind)
  if (session.value?.id === id) session.value = { ...session.value, lastOperation: { id: requestId, kind, status: 'pending', error: null } }
  stopRecognition()
  try {
    const value = await api.generateInterview(id, action, requestId, content)
    applySession(value)
    if (activeId.value === id) {
      if (action === 'messages' && input.value.trim() === content) input.value = ''
      const last = value.messages.at(-1)
      if (last?.role === 'assistant' && last.operationId === requestId && action !== 'review') void speak(last.content)
    }
  } catch {
    try {
      await loadSession(id)
      if (activeId.value === id && session.value?.messages.some(message => message.operationId === requestId && message.role === 'user') && input.value.trim() === content) input.value = ''
    } catch { /* 网络恢复后可刷新记录；输入保持可见。 */ }
  } finally {
    const next = new Map(busyKinds.value); next.delete(id); busyKinds.value = next
    await loadHistory()
    schedulePoll()
  }
}
async function sendAnswer() { if (canSend.value && session.value && input.value.trim()) await perform(session.value.id, 'messages', input.value.trim()) }
async function retryGeneration() { if (session.value && !working.value) await perform(session.value.id, 'retry') }
async function finishInterview() {
  if (!session.value || working.value || !answerCount.value) return
  const ok = await ElMessageBox.confirm('结束本场面试并根据已保存的回答生成复盘？', '生成复盘', { confirmButtonText: '生成复盘', cancelButtonText: '继续面试' }).catch(() => false)
  if (ok && session.value) await perform(session.value.id, 'review')
}
async function refreshCurrent() {
  pollFailures = 0
  await Promise.all([loadResumes(), loadHistory()])
  if (activeId.value) { try { await loadSession(activeId.value); schedulePoll() } catch { /* 保留手动刷新入口。 */ } }
}
async function reloadExported(id: number) { if (activeId.value === id) { try { await loadSession(id) } catch { /* 再次打开时读取已保存状态。 */ } } }
async function removeInterview(record: InterviewSummary) {
  const ok = await ElMessageBox.confirm('删除这场面试的对话和复盘？已加入问答或待办的内容会保留。', '删除面试记录', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }).catch(() => false)
  if (!ok) return
  try { await api.deleteInterview(record.id); if (activeId.value === record.id) await newInterview(); await loadHistory(); ElMessage.success('面试记录已删除') } catch { /* 请求拦截器已提示。 */ }
}
</script>

<style scoped>
.page, .workspace { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.interview-grid { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 20px; align-items: start; }
.section-title { font-size: 14px; font-weight: 650; }
.resume-picker { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; width: 100%; }
.resume-picker .el-select { flex: 1; min-width: 180px; }
.resume-picker .el-button + .el-button { margin-left: 0; }
.setup-fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 16px; margin-top: 20px; }
.material-preview { margin-bottom: 18px; }
.resume-text { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 360px; overflow-y: auto; margin: 0; color: var(--ink-2); line-height: 1.8; font: inherit; font-size: 13px; }
.setup-guide { display: flex; gap: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-sunken); margin: 2px 0 22px; color: var(--ink-2); }
.guide-icon { display: grid; place-items: center; flex: 0 0 32px; height: 32px; border-radius: 9px; background: var(--surface-selected); color: var(--el-color-primary); font-size: 18px; }
.setup-guide strong { color: var(--ink); font-size: 14px; font-weight: 600; }
.setup-guide p { margin: 6px 0 0; font-size: 13px; line-height: 1.8; }
.session-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.session-heading h2 { margin: 0; font-size: 17px; color: var(--ink); overflow-wrap: anywhere; }
.session-heading p { margin: 7px 0 0; font-size: 12px; color: var(--ink-3); line-height: 1.7; }
.snapshot { margin-top: 12px; }
.snapshot :deep(.el-collapse-item__header) { color: var(--ink-3); font-size: 12px; }
.session-tabs :deep(.el-tabs__header) { margin: 0; }
.session-tabs :deep(.el-tabs__content) { display: none; }
.chat-card :deep(.el-card__body) { padding: 20px; }
.chat-scroll { min-height: 300px; height: clamp(320px, 44dvh, 620px); display: flex; flex-direction: column; gap: 20px; overflow-y: auto; padding-right: 6px; }
.message { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
.message.user { align-items: flex-end; }
.speaker { font-size: 11px; color: var(--ink-3); }
.bubble { max-width: 85%; padding: 12px 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface-sunken); overflow-wrap: anywhere; }
.user-bubble { background: var(--surface-selected); color: var(--ink); white-space: pre-wrap; font-size: 14px; line-height: 1.8; }
.thinking { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--ink-2); font-size: 13px; padding: 8px 0; }
.thinking > span:last-child { width: 100%; padding-left: 16px; color: var(--ink-3); font-size: 12px; }
.thinking-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
.input-bar { display: flex; align-items: flex-end; gap: 12px; }
.input-bar .el-textarea { flex: 1; min-width: 0; }
.interview-actions, .voice-actions { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.voice-actions .el-button + .el-button { margin-left: 0; }
.hint { color: var(--ink-3); font-size: 12px; line-height: 1.7; margin: 0; }
.recovery { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
.history-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.history-count { color: var(--ink-3); font-size: 12px; }
.history-card :deep(.el-card__body) { padding: 8px; }
.history-list { max-height: calc(100dvh - 210px); min-height: 130px; overflow-y: auto; }
.history-row { display: flex; align-items: center; border: 1px solid transparent; border-radius: 9px; margin-bottom: 3px; }
.history-row:hover { background: var(--surface-sunken); }
.history-row.active { background: var(--surface-selected); border-color: var(--line); }
.history-link { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; padding: 13px 10px; text-align: left; border: 0; border-radius: 9px; background: transparent; cursor: pointer; font: inherit; }
.history-title { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; color: var(--ink); }
.history-role { color: var(--ink-2); font-size: 12px; overflow-wrap: anywhere; }
.history-meta { display: flex; flex-wrap: wrap; gap: 10px; color: var(--ink-3); font-size: 11px; }
.history-meta .completed { color: var(--el-color-success-dark-2); }
.history-delete { flex-shrink: 0; display: grid; place-items: center; width: 28px; height: 32px; margin-right: 4px; color: var(--ink-3); background: transparent; border: 0; border-radius: 6px; cursor: pointer; opacity: 0; }
.history-row:hover .history-delete, .history-row:focus-within .history-delete { opacity: 1; }
.history-delete:hover { color: var(--el-color-danger); background: var(--el-color-danger-light-9); }
@media (max-width: 1100px) { .interview-grid { grid-template-columns: minmax(0, 1fr) 260px; gap: 16px; } .setup-fields { grid-template-columns: 1fr; gap: 0; } }
@media (max-width: 960px) { .interview-grid { grid-template-columns: minmax(0, 1fr); } .history-list { max-height: 360px; } }
@media (max-width: 760px) { .bubble { max-width: 95%; padding: 10px 12px; } .chat-card :deep(.el-card__body) { padding: 14px; } .input-bar { flex-wrap: wrap; } .input-bar .el-textarea { flex-basis: 100%; } .input-bar .el-button { margin-left: auto; } .setup-guide { padding: 14px; } .history-delete { opacity: 1; } }
@media (hover: none) { .history-delete { opacity: 1; } }
</style>
