<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h1>{{ categoryName }}</h1>
        <p class="sub">共 {{ filtered.length }} 条 · 待复习 {{ learningCount }} 条</p>
      </div>
      <div class="actions">
        <input
          ref="fileInput"
          type="file"
          accept=".md,.markdown,.txt"
          hidden
          @change="onFileChange"
        />
        <el-button icon="Upload" @click="fileInput?.click()">导入</el-button>
        <el-button type="primary" icon="Plus" @click="goCreate">新增问题</el-button>
      </div>
    </div>

    <!-- 工具行 -->
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索问题 / 答案"
        clearable
        prefix-icon="Search"
        style="width: 240px"
      />
      <el-select v-model="filterStatus" placeholder="掌握状态" clearable style="width: 130px">
        <el-option v-for="(label, key) in QA_STATUS_LABELS" :key="key" :label="label" :value="key" />
      </el-select>
      <el-select
        v-model="filterTags"
        multiple
        collapse-tags
        collapse-tags-tooltip
        placeholder="含标签"
        clearable
        style="width: 150px"
      >
        <el-option label="（无标签）" :value="NONE_TAG" class="none-tag-option" />
        <el-option v-for="t in allTags" :key="t" :label="t" :value="t" />
      </el-select>
      <el-select
        v-model="filterExcludeTags"
        multiple
        collapse-tags
        collapse-tags-tooltip
        placeholder="排除标签"
        clearable
        style="width: 150px"
      >
        <el-option v-for="t in allTags" :key="t" :label="t" :value="t" />
      </el-select>
      <span class="spacer" />
      <span v-if="filtered.length > 0" class="select-all">
        <input
          type="checkbox"
          :checked="allSelected"
          @change="toggleSelectAll(($event.target as HTMLInputElement).checked)"
        />
        全选
      </span>
      <el-button
        plain
        icon="PriceTag"
        :disabled="selectedIds.size === 0"
        title="勾选题目后可批量添加 / 移除标签"
        @click="openBatchTagDialog"
      >
        编辑标签
      </el-button>
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

    <!-- 导入预览：解析出题目逐条确认，页面内操作 -->
    <el-card v-if="importPreview" shadow="never" class="list-card">
      <div class="import-head">
        <div>
          <div class="import-title">导入预览</div>
          <div class="import-sub">
            解析出 {{ importPreview.length }} 条 · {{ existCount }} 条已存在将跳过 · 导入到「{{ categoryName }}」
          </div>
        </div>
        <div class="actions">
          <el-button @click="cancelImport">取消</el-button>
          <el-button
            type="primary"
            :loading="importing"
            :disabled="importableCount === 0"
            @click="confirmImport"
          >
            导入 {{ importableCount }} 条
          </el-button>
        </div>
      </div>
      <div class="import-list">
        <div v-for="(p, idx) in importPreview" :key="idx" class="import-row">
          <span class="q-mark">Q</span>
          <span class="import-question">{{ markdownToText(p.question) }}</span>
          <span class="spacer" />
          <el-tag size="small" :type="p.exists ? 'info' : 'success'" effect="plain">
            {{ p.exists ? '已存在 · 跳过' : '将导入' }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 索引列表 -->
    <el-card v-else shadow="never" class="list-card" v-loading="store.loading">
      <template v-if="filtered.length > 0">
        <div class="list">
          <div
            v-for="item in paged"
            :key="item.id"
            class="qa-card"
            :class="{ selected: selectedIds.has(item.id) }"
            @click="onCardClick($event, item)"
          >
            <div class="qa-head">
              <!-- 纯视觉指示：点击由卡片按「左 1/4 选中」统一处理 -->
              <input
                type="checkbox"
                class="pick-box"
                :checked="selectedIds.has(item.id)"
                tabindex="-1"
              />
              <span class="q-mark">Q</span>
              <span class="question">{{ markdownToText(item.question) }}</span>
              <span class="spacer" />
              <el-tag
                class="status-tag"
                :color="QA_STATUS_COLORS[item.status]"
                effect="dark"
                size="small"
                disable-transitions
                title="点击切换掌握状态"
                @click.stop="toggleStatus(item)"
              >
                {{ QA_STATUS_LABELS[item.status] }}
              </el-tag>
            </div>
            <div class="qa-meta">
              <span class="snippet" :class="{ empty: !item.answer }">{{ snippet(item) }}</span>
              <span class="spacer" />
              <span class="read-time num" :class="{ unread: !item.lastReadAt }">
                {{ item.lastReadAt ? `最后阅读 ${dayjs(item.lastReadAt).format('MM-DD HH:mm')}` : '未读' }}
              </span>
            </div>
            <div class="qa-tags">
              <span class="tags-wrap">
                <el-tag v-for="t in sortTags(item.tags)" :key="t" size="small" effect="plain" class="mini-tag">
                  {{ t }}
                </el-tag>
                <span v-if="!item.tags?.length" class="no-tags">无标签</span>
              </span>
              <!-- 卡片上直接打标签：勾选已有 / 输入新建 -->
              <el-popover placement="bottom-end" :width="230" trigger="click">
                <template #reference>
                  <el-icon
                    class="add-tag-btn"
                    role="button"
                    aria-label="编辑标签"
                    title="编辑标签"
                    @click.stop
                  >
                    <Plus />
                  </el-icon>
                </template>
                <el-checkbox-group v-model="item.tags" @change="saveTags(item)">
                  <div class="tag-pick-list">
                    <el-checkbox v-for="t in tagOptions(item)" :key="t" :value="t">{{ t }}</el-checkbox>
                  </div>
                </el-checkbox-group>
                <div class="tag-add">
                  <el-input
                    v-model="newTag"
                    size="small"
                    placeholder="新标签，回车添加"
                    @keyup.enter="addTag(item)"
                  />
                  <el-button size="small" type="primary" plain @click="addTag(item)">添加</el-button>
                </div>
              </el-popover>
            </div>
          </div>
        </div>
        <div class="pager">
          <el-pagination
            v-model:current-page="page"
            :page-size="PAGE_SIZE"
            :total="filtered.length"
            :pager-count="5"
            small
            background
            layout="total, prev, pager, next"
          />
        </div>
      </template>
      <el-empty
        v-else
        description="还没有题目，点击右上角「新增问题」开始积累"
        :image-size="80"
      />
    </el-card>

    <!-- 批量编辑标签：添加 + 移除 -->
    <el-dialog v-model="batchTagVisible" title="批量编辑标签" width="460px">
      <p class="batch-hint">
        对选中的 <b>{{ selectedIds.size }}</b> 条题目：
      </p>
      <div class="form-label">添加标签（逗号分隔，可留空）</div>
      <el-input v-model="batchAddInput" placeholder="如：agent, rag" @keyup.enter="applyBatchTag" />
      <template v-if="batchRemoveCandidates.length">
        <div class="form-label margin-top">移除标签（勾选要从这些题目上移除的，可留空）</div>
        <el-checkbox-group v-model="batchRemoveTags">
          <div class="remove-grid">
            <el-checkbox v-for="t in batchRemoveCandidates" :key="t" :value="t">{{ t }}</el-checkbox>
          </div>
        </el-checkbox-group>
      </template>
      <div v-else class="no-candidate">选中题目还没有任何标签，输入要添加的标签即可</div>
      <template #footer>
        <el-button @click="batchTagVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!canApplyBatchTag" @click="applyBatchTag">
          应用
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QA_STATUS_LABELS, QA_STATUS_COLORS, sortTags } from '../constants'
import { parseQaMarkdown, type ParsedQa } from '../importer'
import * as api from '../api'
import { useQaStore } from '../store'
import { useSettingsStore } from '@/modules/settings/store'
import type { QaItem, QaStatus } from '../types'
import { markdownToText } from '@/shared/utils/markdown'

const route = useRoute()
const router = useRouter()
const store = useQaStore()
const settings = useSettingsStore()

/** 当前分类来自路由参数（分类为用户自建实体） */
const categoryId = computed(() => Number(route.params.id))
const categoryName = computed(
  () => store.categories.find((c) => c.id === categoryId.value)?.name ?? '分类',
)

onMounted(() => store.ensureLoaded())

const keyword = ref('')
const filterStatus = ref<QaStatus | ''>('')
const filterTags = ref<string[]>([])
const filterExcludeTags = ref<string[]>([])

/** 「含标签」下拉的特殊项：勾选 = 筛出未打标签的题目 */
const NONE_TAG = '__none__'

/** 导入状态：null = 非预览态 */
const fileInput = ref<HTMLInputElement>()
const importPreview = ref<(ParsedQa & { exists: boolean })[] | null>(null)
const importing = ref(false)
/** 本次导入的文件名（去扩展名），作为标签候选 */
const importFilenameTag = ref('')

/** 卡片快速打标签的新标签输入 */
const newTag = ref('')

/** 批量删除：跨页累积的选中集合 */
const selectedIds = ref(new Set<number>())

/** 全选 = 选中当前筛选结果下的全部题目（跨页） */
const allSelected = computed(
  () => filtered.value.length > 0 && filtered.value.every((i) => selectedIds.value.has(i.id)),
)

function toggleSelect(id: number) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectAll(checked: boolean | string | number) {
  const next = new Set(selectedIds.value)
  if (checked) filtered.value.forEach((i) => next.add(i.id))
  else filtered.value.forEach((i) => next.delete(i.id))
  selectedIds.value = next
}

/** 点击卡片左 1/4 = 切换选中，其余区域 = 进详情 */
function onCardClick(e: MouseEvent, item: QaItem) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  if (e.clientX - rect.left < rect.width * 0.25) toggleSelect(item.id)
  else goDetail(item)
}

async function confirmBatchRemove() {
  const ids = [...selectedIds.value]
  const ok = await ElMessageBox.confirm(
    `确定删除所选的 ${ids.length} 条题目吗？删除后不可恢复。`,
    '批量删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!ok) return
  for (const id of ids) await api.deleteItem(id)
  await store.loadAll()
  ElMessage.success(`已删除 ${ids.length} 条`)
  selectedIds.value = new Set()
}

/** 批量编辑标签：为所有选中题目添加 / 移除标签 */
const batchTagVisible = ref(false)
const batchAddInput = ref('')
const batchRemoveTags = ref<string[]>([])

/** 移除候选 = 选中题目标签的并集 */
const batchRemoveCandidates = computed(() =>
  [
    ...new Set(
      [...selectedIds.value].flatMap((id) => store.items.find((i) => i.id === id)?.tags ?? []),
    ),
  ].sort((a, b) => a.localeCompare(b, 'zh')),
)

const canApplyBatchTag = computed(
  () => batchAddInput.value.trim().length > 0 || batchRemoveTags.value.length > 0,
)

function openBatchTagDialog() {
  batchAddInput.value = ''
  batchRemoveTags.value = []
  batchTagVisible.value = true
}

async function applyBatchTag() {
  const addTags = batchAddInput.value
    .split(/[,，、\s]+/)
    .map((t) => t.trim())
    .filter(Boolean)
  const removeTags = [...batchRemoveTags.value]
  if (!addTags.length && !removeTags.length) return
  const ids = [...selectedIds.value]
  const byId = new Map(store.items.map((i) => [i.id, i]))
  let changed = 0
  for (const id of ids) {
    const item = byId.get(id)
    if (!item) continue
    let merged = item.tags ?? []
    if (removeTags.length) merged = merged.filter((t) => !removeTags.includes(t))
    if (addTags.length) merged = [...new Set([...merged, ...addTags])]
    const before = item.tags ?? []
    if (before.length !== merged.length || merged.some((t) => !before.includes(t))) {
      await api.updateItem(id, { tags: merged })
      changed++
    }
  }
  await store.loadAll()
  batchTagVisible.value = false
  selectedIds.value = new Set()
  ElMessage.success(`已更新 ${changed} 条题目的标签`)
}

const existCount = computed(() => importPreview.value?.filter((p) => p.exists).length ?? 0)
const importableCount = computed(
  () => (importPreview.value?.length ?? 0) - existCount.value,
)

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 允许重复选择同一文件
  if (!file) return
  importFilenameTag.value = file.name.replace(/\.[^.]+$/, '')
  const parsed = parseQaMarkdown(await file.text())
  if (!parsed.length) {
    ElMessage.warning('未解析出任何题目：请确认格式（## 二级标题为一道问题）')
    return
  }
  importPreview.value = parsed.map((p) => ({
    ...p,
    exists: store.items.some(
      (i) => i.categoryId === categoryId.value && i.question === p.question,
    ),
  }))
}

function cancelImport() {
  importPreview.value = null
}

async function confirmImport() {
  if (!importPreview.value) return
  importing.value = true
  try {
    // 设置开启时，文件名（去扩展名）作为该批题目的公共标签
    const filenameTag = settings.importFilenameAsTag ? importFilenameTag.value : null
    let ok = 0
    for (const p of importPreview.value) {
      if (p.exists) continue
      await api.createItem({
        categoryId: categoryId.value,
        question: p.question,
        answer: p.answer,
        tags: filenameTag ? [filenameTag] : null,
      })
      ok++
    }
    await store.loadAll()
    ElMessage.success(`已导入 ${ok} 条`)
    importPreview.value = null
  } finally {
    importing.value = false
  }
}

/** 索引分页：每页 5 条；页码存 store，从详情返回时回到离开时的页 */
const PAGE_SIZE = 5
const page = ref(store.listPage)

watch(page, (v) => {
  store.listPage = v
})

/** 全部出现过的标签（限定当前分类，去重排序） */
const allTags = computed(() =>
  [
    ...new Set(
      store.items
        .filter((i) => i.categoryId === categoryId.value)
        .flatMap((i) => i.tags ?? []),
    ),
  ].sort((a, b) => a.localeCompare(b, 'zh')),
)

/** 标签勾选候选 = 当前分类标签 + 该题已有标签（自定义不丢失） */
function tagOptions(item: QaItem): string[] {
  return [...new Set([...allTags.value, ...(item.tags ?? [])])]
}

/** 卡片上保存标签（静默） */
async function saveTags(item: QaItem) {
  await store.update(item.id, { tags: item.tags ?? [] }, true)
}

/** 输入新标签并入该题 */
function addTag(item: QaItem) {
  const tag = newTag.value.trim()
  if (!tag) return
  if (!item.tags?.includes(tag)) {
    item.tags = [...(item.tags ?? []), tag]
    void store.update(item.id, { tags: item.tags }, true)
  }
  newTag.value = ''
}

const filtered = computed(() => {
  let list = store.items.filter((i) => i.categoryId === categoryId.value)
  if (keyword.value) {
    const k = keyword.value.toLowerCase()
    list = list.filter(
      (i) => i.question.toLowerCase().includes(k) || (i.answer ?? '').toLowerCase().includes(k),
    )
  }
  if (filterStatus.value) list = list.filter((i) => i.status === filterStatus.value)
  if (filterTags.value.length) {
    const inc = filterTags.value
    const wantsNone = inc.includes(NONE_TAG)
    list = list.filter((i) => {
      const tags = i.tags ?? []
      // 「（无标签）」与普通标签是并列的包含条件（OR）
      if (wantsNone) return tags.length === 0 || tags.some((t) => inc.includes(t))
      return tags.some((t) => inc.includes(t))
    })
  }
  if (filterExcludeTags.value.length) {
    const exc = filterExcludeTags.value
    list = list.filter((i) => !(i.tags ?? []).some((t) => exc.includes(t)))
  }
  // tags 归一为数组（null → []），供卡片勾选绑定
  return list.map((i) => ({ ...i, tags: i.tags ?? [] }))
})

const paged = computed(() =>
  filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE),
)

const learningCount = computed(
  () =>
    store.items.filter(
      (i) => i.categoryId === categoryId.value && i.status === 'learning',
    ).length,
)

// 切换分类时重置视图状态与选择
watch(
  () => route.params.id,
  () => {
    keyword.value = ''
    filterStatus.value = ''
    filterTags.value = []
    filterExcludeTags.value = []
    page.value = 1
    selectedIds.value = new Set()
  },
)

// 搜索 / 筛选变化回第一页；数据变化后页码夹紧
watch([keyword, filterStatus, filterTags, filterExcludeTags], () => {
  page.value = 1
})
watch(filtered, (list) => {
  const maxPage = Math.max(1, Math.ceil(list.length / PAGE_SIZE))
  if (page.value > maxPage) page.value = maxPage
})

function toggleStatus(item: QaItem) {
  void store.patchStatus(item.id, item.status === 'mastered' ? 'learning' : 'mastered')
}

/** 答案摘要：渲染 Markdown 后取纯文本首行，超长截断 */
function snippet(item: QaItem): string {
  const text = markdownToText(item.answer)
  if (!text) return '暂无答案'
  return text.length > 60 ? text.slice(0, 60) + '…' : text
}

function goDetail(item: QaItem) {
  router.push(`/qa/cat/${item.categoryId}/${item.id}`)
}

function goCreate() {
  router.push(`/qa/cat/${categoryId.value}/new`)
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.toolbar .spacer {
  flex: 1;
}

.select-all {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-2);
  white-space: nowrap;
  cursor: pointer;
}

.selected-count {
  font-size: 12.5px;
  color: var(--ink-3);
  white-space: nowrap;
  /* 固定占位：数字位数变化时不挤压左侧的全选与按钮 */
  min-width: 80px;
  font-variant-numeric: tabular-nums;
}

.selected-count.active {
  color: var(--accent);
  font-weight: 600;
}

.select-all input {
  accent-color: var(--el-color-primary);
  cursor: pointer;
}

/* 「（无标签）」特殊项弱化显示 */
:deep(.none-tag-option) {
  color: var(--ink-3);
}

/* 批量编辑标签对话框 */
.batch-hint {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--ink-2);
}

.batch-hint b {
  color: var(--el-color-primary);
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  margin-bottom: 8px;
}

.form-label.margin-top {
  margin-top: 18px;
}

.remove-grid {
  display: flex;
  flex-wrap: wrap;
  column-gap: 14px;
  max-height: 180px;
  overflow-y: auto;
  padding: 2px 4px;
  border: 1px dashed var(--line-soft);
  border-radius: 8px;
}

.no-candidate {
  margin-top: 18px;
  font-size: 12.5px;
  color: var(--ink-3);
}

.pick-box {
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  margin-right: -4px;
  /* 纯视觉指示：点击落到卡片上由「左 1/4 选中」统一处理 */
  pointer-events: none;
  accent-color: var(--el-color-primary);
}

.list-card :deep(.el-card__body) {
  padding: 12px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  /* 固定 5 条容量（卡片实际 106px：问题/摘要/标签三行），不满一页也占位，分页条不漂移 */
  min-height: calc(106px * 5 + 8px * 4);
}

.qa-card {
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  /* 两行卡片（问题/标签+阅读时间），高度恒定 */
  min-height: 76px;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.qa-card:hover {
  border-color: #d8dbe0;
  background: #fafbfc;
}

/* 选中行：整行高亮（左侧指示 + 淡底） */
.qa-card.selected {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
  box-shadow: inset 4px 0 0 var(--el-color-primary);
}

.qa-card.selected:hover {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary);
}

.qa-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-mark {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border-radius: 6px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 700;
  font-size: 13px;
  display: grid;
  place-items: center;
}

.question {
  font-weight: 600;
  color: var(--ink);
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.spacer {
  flex: 1;
}

.status-tag {
  border: none;
  color: #fff;
  font-weight: 600;
  border-radius: 999px;
  cursor: pointer;
}

.qa-meta {
  margin-top: 8px;
  padding-left: 32px;
  display: flex;
  align-items: center;
  gap: 6px;
  /* 单行固定高 */
  min-height: 22px;
  overflow: hidden;
  white-space: nowrap;
}

.snippet {
  color: var(--ink-2);
  font-size: 13px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.snippet.empty {
  color: var(--ink-3);
}

.read-time {
  color: var(--ink-3);
  font-size: 12px;
  flex-shrink: 0;
}

.read-time.unread {
  color: var(--accent);
  font-weight: 600;
}

.mini-tag {
  color: var(--ink-2);
  background: #f2f2f3;
  border-color: transparent;
  flex-shrink: 0;
}

.qa-tags {
  margin-top: 6px;
  padding-left: 32px;
  display: flex;
  align-items: center;
  gap: 6px;
  /* 单行固定高 */
  min-height: 22px;
}

.tags-wrap {
  flex: 1;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  white-space: nowrap;
}

.no-tags {
  color: var(--ink-3);
  font-size: 12px;
}

.add-tag-btn {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  color: var(--ink-3);
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 13px;
  opacity: 0;
  transition:
    opacity 0.15s ease,
    color 0.15s ease,
    background-color 0.15s ease;
}

.qa-card:hover .add-tag-btn {
  opacity: 1;
}

.add-tag-btn:hover {
  color: var(--el-color-primary);
  background: #f1f2f4;
}

.tag-pick-list {
  max-height: 190px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.tag-add {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--line-soft);
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
}

/* 导入预览 */
.import-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.import-title {
  font-size: 14px;
  font-weight: 600;
}

.import-sub {
  margin-top: 2px;
  font-size: 12.5px;
  color: var(--ink-3);
}

.import-list {
  max-height: 430px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.import-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fafafb;
}

.import-question {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13.5px;
  color: var(--ink-2);
}
</style>