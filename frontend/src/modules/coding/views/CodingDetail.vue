<template>
  <div class="coding-workspace" v-loading="loading">
    <header class="workspace-bar">
      <el-button text icon="ArrowLeft" :disabled="busy" @click="back">返回题目</el-button>
      <div v-if="!loadError && !loading" class="workspace-actions">
        <span class="save-state" :class="{ changed: dirty, failed: saveError }" role="status" aria-live="polite">{{ saveState }}</span>
        <el-button v-if="saveError" link type="danger" :disabled="saving || busy" @click="retrySave">重试</el-button>
        <el-button v-if="item" plain type="danger" icon="Delete" :disabled="busy || saving" :loading="deleting" aria-label="删除题目" @click="remove" />
      </div>
    </header>

    <el-result v-if="loadError" icon="warning" title="未能读取手撕题" sub-title="题目或分类可能已删除，也可以重新加载。">
      <template #extra><el-button @click="load">重新加载</el-button></template>
    </el-result>
    <el-form v-else-if="!loading" :model="form" label-position="top" :disabled="busy" @submit.prevent="retrySave">
      <section class="problem-header">
        <el-input v-model="form.title" class="problem-title" maxlength="300" aria-label="题目名称" placeholder="输入题目名称，例如：手写 LRU 缓存" />
        <p class="workspace-caption">{{ item ? `更新于 ${dayjs(item.updatedAt).format('YYYY-MM-DD HH:mm')}` : '新手撕题' }}<span>停止输入 1 秒后自动保存</span></p>
        <div class="metadata-fields">
          <el-form-item label="题目分类" required>
            <el-select v-model="form.categoryId" aria-label="题目分类"><el-option v-for="category in store.categories" :key="category.id" :label="category.name" :value="category.id" /></el-select>
          </el-form-item>
          <el-form-item label="难度"><el-select v-model="form.difficulty" aria-label="题目难度"><el-option v-for="(label, value) in difficulties" :key="value" :label="label" :value="value" /></el-select></el-form-item>
          <el-form-item label="掌握状态"><el-select v-model="form.status" aria-label="掌握状态"><el-option v-for="(label, value) in statuses" :key="value" :label="label" :value="value" /></el-select></el-form-item>
          <el-form-item label="标签"><el-select v-model="form.tags" multiple filterable allow-create default-first-option :multiple-limit="12" aria-label="题目标签" placeholder="输入标签并回车" /></el-form-item>
        </div>
      </section>

      <div class="work-grid">
        <section class="notes-pane">
          <el-tabs v-model="noteTab" class="note-tabs">
            <el-tab-pane label="题目描述" name="description">
              <el-input v-model="form.description" class="note-input" type="textarea" :autosize="{ minRows: 12, maxRows: 24 }" maxlength="30000" aria-label="题目描述" placeholder="记录题目要求、输入输出、示例与边界条件…" />
            </el-tab-pane>
            <el-tab-pane label="思路与复盘" name="approach">
              <el-input v-model="form.approach" class="note-input" type="textarea" :autosize="{ minRows: 12, maxRows: 24 }" maxlength="30000" aria-label="解题思路与复盘" placeholder="记录实现步骤、易错点与再次手写时需要注意的地方…" />
            </el-tab-pane>
          </el-tabs>
          <div class="note-footer">
            <el-form-item label="时间 / 空间复杂度"><el-input v-model="form.complexity" maxlength="1000" aria-label="时间 / 空间复杂度" placeholder="例如：时间 O(n)，空间 O(n)" /></el-form-item>
            <el-form-item label="来源链接（可选）"><el-input v-model="form.sourceUrl" maxlength="2000" aria-label="来源链接" placeholder="题库或面经链接"><template #append><a v-if="sourceLink" :href="sourceLink" target="_blank" rel="noopener noreferrer">打开</a><span v-else>链接</span></template></el-input></el-form-item>
          </div>
        </section>

        <section class="code-pane" aria-label="代码工作区">
          <div class="code-toolbar">
            <div class="code-title"><span>代码实现</span><el-select v-model="form.language" class="language-select" size="small" filterable allow-create default-first-option aria-label="编程语言"><el-option v-for="language in codingLanguages" :key="language" :label="language" :value="language" /></el-select></div>
            <div class="editor-actions">
              <el-button text size="small" :disabled="busy" title="显示代码补全（Ctrl+Space）" @click="codeEditor?.complete()">补全</el-button>
              <el-button text size="small" :type="wrapped ? 'primary' : undefined" :aria-pressed="wrapped" @click="wrapped = !wrapped">自动换行</el-button>
              <el-button text size="small" :disabled="!form.code" @click="copyCode">复制代码</el-button>
            </div>
          </div>
          <CodeEditor ref="codeEditor" v-model="form.code" :language="form.language" :readonly="busy" :wrapped="wrapped" class="code-surface" />
          <div class="code-help"><span>Ctrl + Space 补全 · Tab 接受提示 · 自动保存</span><span :class="{ 'limit-error': codeTooLong }">{{ form.code.length.toLocaleString() }} / 100,000 字符{{ codeTooLong ? '，请精简后保存' : '' }}</span></div>
        </section>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import CodeEditor from '../components/CodeEditor.vue'
import { codingLanguages } from '../editor'
import { fetchItem } from '../api'
import { createAutosave } from '../autosave'
import { useCodingStore } from '../store'
import { difficulties, statuses, type CodingItem, type CodingPayload } from '../types'

const route = useRoute(), router = useRouter(), store = useCodingStore()
const isNew = computed(() => route.name === 'coding-new')
const item = ref<CodingItem | null>(null)
const loading = ref(true), loadError = ref(false), saving = ref(false), deleting = ref(false)
// 自动保存期间继续接收输入，只在删除时锁定工作区。
const busy = computed(() => deleting.value)
const noteTab = ref('description'), wrapped = ref(false)
const codeEditor = ref<InstanceType<typeof CodeEditor>>()
const blank = (): CodingPayload => ({ categoryId: Number(route.params.id), title: '', sourceUrl: '', description: '', language: 'Python', code: '', approach: '', complexity: '', difficulty: 'medium', status: 'todo', tags: [] })
const form = reactive<CodingPayload>(blank())
const baseline = ref('')
let generation = 0
let leaving = false
let internalRouteTarget = ''
let retries = 0
const saveError = ref('')
const dirty = computed(() => !!baseline.value && JSON.stringify(form) !== baseline.value)
const codeTooLong = computed(() => form.code.length > 100000)
const sourceLink = computed(() => {
  try { const url = new URL(form.sourceUrl); return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : '' }
  catch { return '' }
})
const validationMessage = computed(() => {
  if (!form.title.trim()) return '填写题目名称后自动保存'
  if (!form.language.trim() || form.language.trim().length > 40) return '编程语言请填写 1–40 个字符'
  if (codeTooLong.value) return '代码过长，请精简后自动保存'
  if (form.sourceUrl.trim() && !sourceLink.value) return '来源链接须为完整的 HTTP(S) 地址'
  if (form.tags.some(tag => tag.trim().length > 40)) return '每个标签不能超过 40 个字符'
  return ''
})
const canSave = computed(() => !loading.value && !loadError.value && !busy.value && !!form.categoryId && !validationMessage.value)
const saveState = computed(() => saving.value ? '正在自动保存…' : saveError.value || (dirty.value ? validationMessage.value || '等待自动保存…' : item.value ? '已保存' : '填写题目名称后自动保存'))
const payload = (value: CodingPayload): CodingPayload => ({ categoryId: value.categoryId, title: value.title,
  sourceUrl: value.sourceUrl, description: value.description, language: value.language, code: value.code,
  approach: value.approach, complexity: value.complexity, difficulty: value.difficulty, status: value.status, tags: [...value.tags] })
const autosave = createAutosave({
  read: () => payload(form), dirty: () => dirty.value, valid: () => canSave.value,
  saving: value => { saving.value = value; if (value) saveError.value = '' },
  write: async snapshot => {
    const current = generation
    const value = await store.save(snapshot, item.value?.id, true)
    if (current !== generation) return
    item.value = value
    // 只在未继续输入时回填服务端规范化的内容，避免旧响应覆盖新代码。
    if (JSON.stringify(form) === JSON.stringify(snapshot)) Object.assign(form, payload(value))
    baseline.value = JSON.stringify(payload(value))
    retries = 0
    const target = `/coding/cat/${value.categoryId}/${value.id}`
    if (!leaving && route.path !== target) {
      internalRouteTarget = target
      try { await router.replace(target) } finally { internalRouteTarget = '' }
    }
  },
  failed: (error, snapshot) => {
    const status = (error as { response?: { status?: number } }).response?.status
    const retryable = !status || status >= 500 || status === 429
    const delay = [3000, 10000, 30000][retries++]
    // 新建请求未确认成功时不自动反复 POST；保留输入并允许用户重试。
    const retry = retryable && !!item.value && delay !== undefined
    saveError.value = retry ? '自动保存失败，稍后重试' : '自动保存失败，内容仍保留在当前页'
    if (!retryable && JSON.stringify(form) !== JSON.stringify(snapshot) && canSave.value) return 0
    return retry ? delay : null
  },
})
watch(() => JSON.stringify(form), () => {
  if (loading.value || loadError.value || busy.value) return
  saveError.value = ''; retries = 0
  autosave.schedule()
})

function adopt(value: CodingItem | null) {
  item.value = value
  Object.assign(form, value ? { categoryId: value.categoryId, title: value.title, sourceUrl: value.sourceUrl,
    description: value.description, language: value.language, code: value.code, approach: value.approach,
    complexity: value.complexity, difficulty: value.difficulty, status: value.status, tags: [...value.tags] } : blank())
  baseline.value = JSON.stringify(form)
}
async function load() {
  autosave.cancel()
  saveError.value = ''; retries = 0
  const current = ++generation
  loading.value = true; loadError.value = false
  try {
    if (store.failed) await store.loadAll()
    else await store.ensureLoaded()
    if (current !== generation) return
    if (store.failed || !store.categories.some(row => row.id === Number(route.params.id))) throw new Error('分类不可用')
    const value = isNew.value ? null : await fetchItem(Number(route.params.itemId))
    if (current !== generation) return
    adopt(value)
  } catch {
    if (current === generation) { item.value = null; baseline.value = ''; loadError.value = true }
  } finally { if (current === generation) loading.value = false }
}
async function canLeave(to: { path: string }) {
  if (to.path === internalRouteTarget) return true
  if (busy.value) return false
  leaving = true
  try {
    if (await autosave.flush()) return true
    autosave.cancel()
    const discard = await ElMessageBox.confirm('当前修改尚未保存成功。继续编写可保留内容并重试，仍要离开吗？', '修改尚未保存', {
      type: 'warning', confirmButtonText: '放弃未保存修改', cancelButtonText: '继续编写',
    }).then(() => true).catch(() => false)
    if (discard) autosave.cancel()
    else autosave.schedule()
    return discard
  } finally { leaving = false }
}
function listPath() { return `/coding/cat/${item.value?.categoryId ?? Number(route.params.id)}` }
function back() { void router.push(listPath()) }
async function retrySave() { saveError.value = ''; retries = 0; await autosave.flush() }
async function remove() {
  if (!item.value || busy.value || saving.value) return
  autosave.cancel()
  const confirmed = await ElMessageBox.confirm(`删除「${item.value.title}」及其代码和复盘记录？`, '删除手撕题', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!confirmed) { autosave.schedule(); return }
  autosave.cancel()
  deleting.value = true
  try {
    // 等待此前已发送的保存请求结束，避免保存与删除交叉。
    await autosave.wait()
    await store.remove(item.value.id)
    baseline.value = JSON.stringify(form)
    deleting.value = false
    await router.replace(listPath())
  } catch { /* 失败时保留当前工作区。 */ }
  finally { deleting.value = false; autosave.schedule() }
}
async function copyCode() {
  try { await navigator.clipboard.writeText(form.code); ElMessage.success('代码已复制') }
  catch { ElMessage.warning('复制失败，请手动选择代码复制') }
}
function handleSaveKey(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 's') {
    event.preventDefault()
    event.stopPropagation()
    void retrySave()
  }
}
function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value || busy.value) { event.preventDefault(); event.returnValue = '' }
}
watch(() => route.fullPath, () => {
  // 新题目首次保存或移动分类后的地址变化不重复加载当前题目。
  if (!isNew.value && item.value?.id === Number(route.params.itemId) && item.value.categoryId === Number(route.params.id)) return
  void load()
}, { immediate: true })
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
onMounted(() => {
  window.addEventListener('keydown', handleSaveKey, true)
  window.addEventListener('beforeunload', handleBeforeUnload)
})
onBeforeUnmount(() => {
  ++generation
  autosave.dispose()
  window.removeEventListener('keydown', handleSaveKey, true)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped>
.coding-workspace { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.workspace-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; position: sticky; top: -4px; z-index: 5; background: var(--paper); padding-block: 10px; }
.workspace-actions, .code-title, .editor-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.workspace-actions { justify-content: flex-end; }
.workspace-actions .el-button + .el-button, .editor-actions .el-button + .el-button { margin-left: 0; }
.save-state { color: var(--ink-3); font-size: 12px; margin-right: 8px; }
.save-state.changed { color: #996018; }
.save-state.failed { color: var(--el-color-danger); }
.save-state::before { content: ''; display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; background: currentColor; vertical-align: 2px; }
.problem-header { margin-bottom: 22px; }
.problem-title { font-size: 25px; font-weight: 650; }
.problem-title :deep(.el-input__wrapper) { background: transparent; padding: 2px 0 8px; box-shadow: none; border-radius: 0; }
.problem-title :deep(.el-input__wrapper.is-focus) { box-shadow: 0 2px 0 var(--accent); }
.problem-title :deep(.el-input__inner) { height: 40px; color: var(--ink); text-overflow: ellipsis; }
.workspace-caption { margin: 8px 0 20px; font-size: 12px; color: var(--ink-3); display: flex; gap: 16px; flex-wrap: wrap; }
.metadata-fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 0.7fr) minmax(0, 0.8fr) minmax(0, 1.6fr); gap: 0 16px; }
.metadata-fields .el-form-item { margin-bottom: 0; }
.metadata-fields .el-select { width: 100%; }
.work-grid { display: grid; grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.5fr); gap: 22px; align-items: start; }
.notes-pane, .code-pane { min-width: 0; border: 1px solid var(--line); border-radius: var(--radius-card); background: var(--card); }
.notes-pane { padding: 2px 20px 0; }
.note-tabs :deep(.el-tabs__header) { margin-bottom: 10px; }
.note-tabs :deep(.el-tabs__item) { height: 48px; }
.note-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: var(--line); }
.note-input :deep(textarea) { padding: 10px 0; line-height: 1.95; font-size: 14px; color: var(--ink-2); border-radius: 0; box-shadow: none; resize: vertical; }
.note-input :deep(textarea:focus) { box-shadow: inset 2px 0 0 var(--el-color-primary-light-7); padding-left: 12px; }
.note-footer { border-top: 1px solid var(--line); padding-top: 18px; margin-top: 18px; }
.note-footer :deep(.el-input-group__append) { padding-inline: 12px; }
.note-footer a { color: var(--el-color-primary); text-decoration: none; }
.code-pane { overflow: hidden; }
.code-pane:focus-within { border-color: var(--el-color-primary-light-5); }
.code-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--line); }
.code-title { font-size: 13px; font-weight: 600; gap: 12px; }
.language-select { width: 128px; font-weight: 400; }
.editor-actions { gap: 0; }
.code-surface { height: clamp(480px, calc(100dvh - 380px), 850px); }
.code-help { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 10px 14px; font-size: 11px; line-height: 1.6; color: var(--ink-3); }
.limit-error { color: var(--el-color-danger); }
@media (max-width: 1100px) { .work-grid { grid-template-columns: 1fr; } .metadata-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 16px; } }
@media (max-width: 600px) {
  .workspace-bar { flex-wrap: wrap; top: -8px; gap: 8px; }
  .workspace-actions { width: 100%; justify-content: flex-end; }
  .save-state { margin-right: auto; font-size: 11px; }
  .workspace-actions .el-button { padding-inline: 10px; }
  .problem-title { font-size: 21px; }
  .workspace-caption { gap: 6px; flex-direction: column; }
  .work-grid { gap: 16px; }
  .notes-pane { padding-inline: 14px; }
  .code-toolbar { padding-inline: 10px; gap: 6px; }
  .code-surface { height: 480px; }
}
</style>
