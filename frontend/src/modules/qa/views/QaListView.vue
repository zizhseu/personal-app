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
        placeholder="标签"
        clearable
        style="width: 170px"
      >
        <el-option v-for="t in allTags" :key="t" :label="t" :value="t" />
      </el-select>
      <span class="spacer" />
      <span v-if="paged.length > 0" class="select-all">
        <input
          type="checkbox"
          :checked="allPageSelected"
          @change="toggleSelectPage(($event.target as HTMLInputElement).checked)"
        />
        全选本页
      </span>
      <el-button
        v-if="selectedIds.size > 0"
        type="danger"
        plain
        icon="Delete"
        @click="confirmBatchRemove"
      >
        删除所选 ({{ selectedIds.size }})
      </el-button>
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
          <div v-for="item in paged" :key="item.id" class="qa-card" @click="goDetail(item)">
            <div class="qa-head">
              <input
                type="checkbox"
                class="pick-box"
                :checked="selectedIds.has(item.id)"
                @click.stop.prevent="toggleSelect(item.id)"
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
              <el-tag v-for="t in item.tags ?? []" :key="t" size="small" effect="plain" class="mini-tag">
                {{ t }}
              </el-tag>
              <span class="read-time num" :class="{ unread: !item.lastReadAt }">
                {{ item.lastReadAt ? `最后阅读 ${dayjs(item.lastReadAt).format('MM-DD HH:mm')}` : '未读' }}
              </span>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QA_STATUS_LABELS, QA_STATUS_COLORS } from '../constants'
import { parseQaMarkdown, type ParsedQa } from '../importer'
import * as api from '../api'
import { useQaStore } from '../store'
import type { QaItem, QaStatus } from '../types'
import { markdownToText } from '@/shared/utils/markdown'

const route = useRoute()
const router = useRouter()
const store = useQaStore()

/** 当前分类来自路由参数（分类为用户自建实体） */
const categoryId = computed(() => Number(route.params.id))
const categoryName = computed(
  () => store.categories.find((c) => c.id === categoryId.value)?.name ?? '分类',
)

onMounted(() => store.ensureLoaded())

const keyword = ref('')
const filterStatus = ref<QaStatus | ''>('')
const filterTags = ref<string[]>([])

/** 导入状态：null = 非预览态 */
const fileInput = ref<HTMLInputElement>()
const importPreview = ref<(ParsedQa & { exists: boolean })[] | null>(null)
const importing = ref(false)

/** 批量删除：跨页累积的选中集合 */
const selectedIds = ref(new Set<number>())

const allPageSelected = computed(
  () => paged.value.length > 0 && paged.value.every((i) => selectedIds.value.has(i.id)),
)

function toggleSelect(id: number) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectPage(checked: boolean | string | number) {
  const next = new Set(selectedIds.value)
  if (checked) paged.value.forEach((i) => next.add(i.id))
  else paged.value.forEach((i) => next.delete(i.id))
  selectedIds.value = next
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

const existCount = computed(() => importPreview.value?.filter((p) => p.exists).length ?? 0)
const importableCount = computed(
  () => (importPreview.value?.length ?? 0) - existCount.value,
)

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 允许重复选择同一文件
  if (!file) return
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
    let ok = 0
    for (const p of importPreview.value) {
      if (p.exists) continue
      await api.createItem({
        categoryId: categoryId.value,
        question: p.question,
        answer: p.answer,
        tags: null,
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

/** 索引分页：每页 5 条 */
const PAGE_SIZE = 5
const page = ref(1)

/** 全部出现过的标签（去重排序，筛选下拉共用） */
const allTags = computed(() =>
  [...new Set(store.items.flatMap((i) => i.tags ?? []))].sort((a, b) =>
    a.localeCompare(b, 'zh'),
  ),
)

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
    list = list.filter((i) => (i.tags ?? []).some((t) => filterTags.value.includes(t)))
  }
  return list
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
    page.value = 1
    selectedIds.value = new Set()
  },
)

// 搜索 / 筛选变化回第一页；数据变化后页码夹紧
watch([keyword, filterStatus, filterTags], () => {
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

.select-all input {
  accent-color: var(--el-color-primary);
  cursor: pointer;
}

.pick-box {
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  margin-right: -4px;
  cursor: pointer;
  accent-color: var(--el-color-primary);
}

.list-card :deep(.el-card__body) {
  padding: 12px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  /* 固定 5 条容量：不足一页时也占位，分页条位置不随条数漂移 */
  min-height: calc(76px * 5 + 8px * 4);
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