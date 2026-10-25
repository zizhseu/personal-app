<template>
  <div class="todo-page">
    <div class="page-head">
      <div class="heading">
        <h1>{{ editing ? (editingId === null ? '新增待办' : '编辑待办') : category?.name ?? '待办事项' }}</h1>
        <p class="sub" v-if="category">
          <template v-if="editing">{{ category.name }} · 待办事项</template>
          <template v-else>共 {{ categoryItems.length }} 条 · 未完成 {{ pendingCount }} 条 · 已完成 {{ completedCount }} 条</template>
        </p>
        <p class="sub" v-else>从侧栏选择一个目录，开始整理待办</p>
      </div>
      <div class="actions" v-if="category && !store.failed && !editing">
        <el-button type="primary" :icon="Plus" :disabled="store.loading" @click="openEditor()">新增待办</el-button>
      </div>
    </div>

    <template v-if="category && !store.failed">
      <div v-if="!editing" class="toolbar">
        <el-input v-model="keyword" placeholder="搜索标题 / 备注" clearable :prefix-icon="Search" class="search" aria-label="搜索待办" />
        <el-select v-model="statusFilter" class="status-filter" aria-label="筛选待办状态">
          <el-option label="全部状态" value="all" />
          <el-option label="未完成" value="pending" />
          <el-option label="已完成" value="completed" />
          <el-option label="已逾期" value="overdue" />
        </el-select>
        <span class="sort-hint">未完成优先 · 按截止时间排序</span>
        <span v-if="filtered.length > 0" class="select-all">
          <input type="checkbox" :checked="allSelected" aria-label="全选待办" @change="toggleSelectAll(($event.target as HTMLInputElement).checked)" />
          全选
        </span>
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="selectedIds.size === 0"
          @click="confirmBatchRemove"
        >
          删除所选
        </el-button>
        <span class="selected-count num" :class="{ active: selectedIds.size > 0 }">
          已选 {{ selectedIds.size }} 条
        </span>
      </div>

      <el-card v-if="editing" shadow="never" class="editor-card">
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="editor" @submit.prevent="saveItem">
          <el-form-item label="标题" prop="title">
            <el-input ref="titleInput" v-model="form.title" placeholder="要完成什么事情？" maxlength="200" show-word-limit :disabled="saving" />
          </el-form-item>
          <el-form-item label="截止时间（选填）" prop="dueAt">
            <el-date-picker v-model="form.dueAt" type="datetime" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="不限时间" clearable :disabled="saving" />
          </el-form-item>
          <el-form-item label="备注（选填）" prop="note">
            <el-input v-model="form.note" type="textarea" :rows="9" maxlength="10000" show-word-limit placeholder="记录具体步骤、注意事项或相关资料" :disabled="saving" />
          </el-form-item>
        </el-form>
        <div class="editor-actions">
          <span class="shortcut-hint">Ctrl + S 快速保存</span>
          <el-button :disabled="saving" @click="closeEditor">取消</el-button>
          <el-button type="primary" :disabled="!form.title.trim()" :loading="saving" @click="saveItem">保存待办</el-button>
        </div>
      </el-card>

      <el-card v-else shadow="never" class="list-card" v-loading="store.loading">
        <div class="task-list">
          <article
            v-for="item in paged"
            :key="item.id"
            class="task-row"
            :class="{ completed: item.completed, overdue: isOverdue(item), selected: selectedIds.has(item.id) }"
            @click="onRowClick($event, item)"
          >
            <input
              class="done-checkbox"
              type="checkbox"
              :checked="item.completed"
              :disabled="busyIds.has(item.id)"
              :aria-label="(item.completed ? '恢复待办：' : '标记完成：') + item.title"
              @click.stop
              @change="toggleCompleted(item, $event)"
            />
            <div class="task-body">
              <div class="task-heading">
                <span class="task-title" :title="item.title">{{ item.title }}</span>
                <span class="state-label" :class="{ done: item.completed, late: isOverdue(item) }">{{ item.completed ? '已完成' : isOverdue(item) ? '已逾期' : '未完成' }}</span>
              </div>
              <p class="note-preview" :class="{ empty: !item.note }">{{ item.note || '暂无备注' }}</p>
              <div class="task-meta num">
                <span :class="{ 'due-late': isOverdue(item) }">{{ item.dueAt ? '截止 ' + formatTime(item.dueAt) : '不限时间' }}</span>
                <span v-if="item.completedAt">完成于 {{ formatTime(item.completedAt) }}</span>
              </div>
            </div>
          </article>
          <el-empty v-if="!paged.length && !store.loading" :description="emptyDescription" :image-size="80" class="list-empty" />
        </div>
        <div class="pager">
          <el-pagination v-model:current-page="page" :page-size="PAGE_SIZE" :total="filtered.length" :pager-count="5" size="small" background layout="total, prev, pager, next" />
        </div>
      </el-card>
    </template>

    <el-card v-else shadow="never" class="empty-card" v-loading="store.loading">
      <el-empty v-if="store.failed" description="待办加载失败，请重试">
        <el-button @click="store.loadAll">重新加载</el-button>
      </el-empty>
      <el-empty v-else-if="route.params.id && store.loaded" description="该目录不存在或已删除" />
      <el-empty v-else-if="store.loaded" :description="store.categories.length ? '请从侧栏选择待办目录' : '点击侧栏「待办事项」旁的 + 创建目录'" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type InputInstance } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useTodoStore } from '../store'
import type { TodoItem } from '../types'

const route = useRoute()
const store = useTodoStore()
const categoryId = computed(() => Number(route.params.id))
const category = computed(() => store.categories.find((item) => item.id === categoryId.value))
const categoryItems = computed(() => store.items.filter((item) => item.categoryId === categoryId.value))
const pendingCount = computed(() => categoryItems.value.filter((item) => !item.completed).length)
const completedCount = computed(() => categoryItems.value.length - pendingCount.value)
const keyword = ref('')
const statusFilter = ref<'all' | 'pending' | 'completed' | 'overdue'>('all')
const PAGE_SIZE = 5
const page = ref(1)
const now = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  void store.ensureLoaded()
  clockTimer = setInterval(() => { now.value = Date.now() }, 30_000)
  window.addEventListener('keydown', onEditorKeydown)
})
onUnmounted(() => {
  clearInterval(clockTimer)
  window.removeEventListener('keydown', onEditorKeydown)
})

/** 编辑态 Ctrl+S / ⌘S 快速保存 */
function onEditorKeydown(e: KeyboardEvent) {
  if (!editing.value) return
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault()
    void saveItem()
  }
}

function isOverdue(item: TodoItem) {
  return !item.completed && !!item.dueAt && dayjs(item.dueAt).valueOf() < now.value
}
function formatTime(value: string) {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

const filtered = computed(() => {
  const term = keyword.value.trim().toLocaleLowerCase()
  return categoryItems.value.filter((item) => {
    if (term && ![item.title, item.note ?? ''].some((text) => text.toLocaleLowerCase().includes(term))) return false
    if (statusFilter.value === 'pending') return !item.completed
    if (statusFilter.value === 'completed') return item.completed
    if (statusFilter.value === 'overdue') return isOverdue(item)
    return true
  }).sort((a, b) => {
    if (a.completed !== b.completed) return Number(a.completed) - Number(b.completed)
    if (a.completed) return (b.completedAt ?? '').localeCompare(a.completedAt ?? '') || b.id - a.id
    if (a.dueAt && b.dueAt) return a.dueAt.localeCompare(b.dueAt) || b.id - a.id
    if (a.dueAt || b.dueAt) return a.dueAt ? -1 : 1
    return b.id - a.id
  })
})
const paged = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))
const emptyDescription = computed(() => categoryItems.value.length === 0
  ? '还没有待办，点击右上角「新增待办」开始记录'
  : '没有符合条件的待办，试试调整搜索或状态筛选')
watch([keyword, statusFilter], () => { page.value = 1 })
watch(() => filtered.value.length, (length) => { page.value = Math.min(page.value, Math.max(1, Math.ceil(length / PAGE_SIZE))) })
watch(categoryId, () => {
  keyword.value = ''
  statusFilter.value = 'all'
  page.value = 1
  selectedIds.value = new Set()
  closeEditor()
})

const editing = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const formRef = ref<FormInstance>()
const titleInput = ref<InputInstance>()
const form = reactive({ title: '', note: '', dueAt: null as string | null })
const rules: FormRules = {
  title: [{ required: true, whitespace: true, message: '请输入待办标题', trigger: 'blur' }],
}

function openEditor(item?: TodoItem) {
  editingId.value = item?.id ?? null
  Object.assign(form, { title: item?.title ?? '', note: item?.note ?? '', dueAt: item?.dueAt ?? null })
  editing.value = true
  void nextTick(() => {
    formRef.value?.clearValidate()
    titleInput.value?.focus()
  })
}
function closeEditor() {
  editing.value = false
  editingId.value = null
}
async function saveItem() {
  if (saving.value || !category.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const targetCategory = categoryId.value
  const targetId = editingId.value
  const payload = { title: form.title.trim(), note: form.note.trim() || null, dueAt: form.dueAt || null }
  saving.value = true
  try {
    const saved = targetId === null
      ? await store.create({ ...payload, categoryId: targetCategory })
      : await store.update(targetId, payload)
    // 切换目录后，旧请求只更新数据，不改变新目录的视图。
    if (categoryId.value === targetCategory && editingId.value === targetId) {
      closeEditor()
      keyword.value = ''
      statusFilter.value = 'all'
      await nextTick()
      const index = filtered.value.findIndex((item) => item.id === saved.id)
      page.value = Math.floor(Math.max(0, index) / PAGE_SIZE) + 1
    }
  } catch { /* 请求拦截器提示错误；保留输入以便重试。 */ }
  finally { saving.value = false }
}

const busyIds = ref(new Set<number>())
function setBusy(id: number, busy: boolean) {
  const next = new Set(busyIds.value)
  if (busy) next.add(id)
  else next.delete(id)
  busyIds.value = next
}
async function toggleCompleted(item: TodoItem, event: Event) {
  // 等保存成功再改变勾选状态，失败时不会留下错误的视觉状态。
  ;(event.target as HTMLInputElement).checked = item.completed
  if (busyIds.value.has(item.id)) return
  setBusy(item.id, true)
  try {
    await store.update(item.id, { completed: !item.completed }, true)
    now.value = Date.now()
    ElMessage.success(item.completed ? '已恢复为待办' : '已标记完成')
  } catch { /* 请求拦截器已提示错误。 */ }
  finally { setBusy(item.id, false) }
}

// ---------- 批量选择（点击行左 1/4 选中，右 3/4 进入编辑主体） ----------
const selectedIds = ref(new Set<number>())

/** 全选 = 选中当前筛选结果下的全部待办（跨页） */
const allSelected = computed(
  () => filtered.value.length > 0 && filtered.value.every((item) => selectedIds.value.has(item.id)),
)

function toggleSelect(id: number) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectAll(checked: boolean | string | number) {
  const next = new Set(selectedIds.value)
  if (checked) filtered.value.forEach((item) => next.add(item.id))
  else filtered.value.forEach((item) => next.delete(item.id))
  selectedIds.value = next
}

function onRowClick(e: MouseEvent, item: TodoItem) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  if (e.clientX - rect.left < rect.width * 0.25) toggleSelect(item.id)
  else openEditor(item)
}

async function confirmBatchRemove() {
  const ids = [...selectedIds.value]
  const confirmed = await ElMessageBox.confirm(`确定删除所选的 ${ids.length} 条待办吗？删除后不可恢复。`, '批量删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!confirmed) return
  try {
    await store.removeMany(ids)
    selectedIds.value = new Set()
  } catch { /* 请求拦截器已提示错误。 */ }
}
</script>

<style scoped>
.todo-page { display: flex; flex-direction: column; gap: 18px; }
.heading { min-width: 0; }
.heading h1 { overflow-wrap: anywhere; }
.actions .el-button + .el-button { margin-left: 0; }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.search { width: 260px; }
.status-filter { width: 140px; }
.sort-hint { margin-left: auto; color: var(--ink-2); font-size: 12px; }
.select-all { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--ink-2); white-space: nowrap; cursor: pointer; }
.select-all input { accent-color: var(--el-color-primary); cursor: pointer; }
.selected-count { min-width: 80px; font-size: 12.5px; color: var(--ink-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
.selected-count.active { color: var(--accent); font-weight: 600; }
.list-card :deep(.el-card__body) { padding: 12px; }
.task-list { min-height: 502px; display: flex; flex-direction: column; gap: 8px; }
.task-row { height: 94px; flex-shrink: 0; display: flex; align-items: center; gap: 14px; padding: 12px 14px; border: 1px solid var(--line-soft); border-radius: 10px; cursor: pointer; transition: border-color 0.15s ease, background-color 0.15s ease; }
.task-row:hover { border-color: var(--line); background: var(--paper); }
/* 选中行：整行高亮（与面试问答列表一致，左侧指示 + 淡底） */
.task-row.selected { border-color: var(--el-color-primary-light-5); background: var(--el-color-primary-light-9); box-shadow: inset 4px 0 0 var(--el-color-primary); }
.task-row.selected:hover { background: var(--el-color-primary-light-9); border-color: var(--el-color-primary); }
.done-checkbox { width: 18px; height: 18px; margin: 0; flex-shrink: 0; cursor: pointer; accent-color: var(--el-color-primary); }
.done-checkbox:disabled { cursor: wait; }
.task-body { flex: 1; min-width: 0; }
.task-heading { display: flex; align-items: center; gap: 10px; min-width: 0; }
.task-title { min-width: 0; color: var(--ink); font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.completed .task-title { text-decoration: line-through; color: var(--ink-2); }
.state-label { flex-shrink: 0; font-size: 11px; color: var(--ink-2); background: var(--paper); padding: 2px 6px; border-radius: 4px; }
.state-label.done { color: var(--el-color-success-dark-2); background: var(--el-color-success-light-9); }
.state-label.late { color: var(--el-color-danger-dark-2); background: var(--el-color-danger-light-9); }
.note-preview { margin: 5px 0; color: var(--ink-2); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.note-preview.empty { color: var(--ink-3); }
.task-meta { display: flex; gap: 14px; color: var(--ink-2); font-size: 11px; white-space: nowrap; overflow: hidden; }
.due-late { color: var(--el-color-danger-dark-2); }
.pager { min-height: 44px; display: flex; align-items: flex-end; justify-content: flex-end; }
.list-empty { flex: 1; }
.editor-card, .empty-card { min-height: 572px; }
.editor { width: 100%; }
.editor :deep(.el-textarea__inner) { resize: vertical; }
.editor-actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; margin-top: 6px; }
.editor-actions .shortcut-hint { margin-right: auto; font-size: 12px; color: var(--ink-3); }
.done-checkbox:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
@media (max-width: 760px) {
  .search { flex: 1; min-width: 160px; }
  .sort-hint { width: 100%; margin-left: 0; }
  .task-row { gap: 9px; padding: 10px; }
  .task-meta { display: block; }
  .task-meta span { display: block; overflow: hidden; text-overflow: ellipsis; }
  .task-heading { gap: 6px; }
}
</style>
