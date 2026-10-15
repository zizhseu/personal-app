<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-head">
      <div>
        <h1>{{ categoryName }}</h1>
        <p class="sub">共 {{ filtered.length }} 题 · 单选 {{ singleCount }} · 多选 {{ multiCount }}</p>
      </div>
      <div class="actions">
        <el-button icon="MagicStick" @click="openAiImport">AI 导入</el-button>
        <el-button type="primary" icon="Plus" @click="goCreate">新增题目</el-button>
      </div>
    </div>

    <!-- 工具行 -->
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索题目 / 选项 / 解析"
        clearable
        prefix-icon="Search"
        style="width: 240px"
      />
      <el-select v-model="filterType" placeholder="题型" clearable style="width: 110px">
        <el-option label="单选" value="single" />
        <el-option label="多选" value="multi" />
      </el-select>
      <span class="spacer" />
      <span class="count num">已收录 {{ store.items.length }} 题</span>
    </div>

    <!-- 题目列表 -->
    <el-card shadow="never" class="list-card" v-loading="store.loading">
      <template v-if="filtered.length > 0">
        <div class="list">
          <div
            v-for="item in paged"
            :key="item.id"
            class="quiz-card"
            @click="goDetail(item)"
          >
            <div class="quiz-head">
              <el-tag size="small" :type="item.qtype === 'multi' ? 'warning' : 'primary'" effect="plain" class="type-tag">
                {{ item.qtype === 'multi' ? '多选' : '单选' }}
              </el-tag>
              <span class="question">{{ item.question }}</span>
              <span class="spacer" />
              <span class="answer num">答案 {{ answerText(item) }}</span>
            </div>
            <div class="quiz-meta">
              <span class="options-preview">{{ item.options.map((o, i) => letter(i) + '. ' + o).join('　') }}</span>
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
        description="还没有题目，点击右上角「新增题目」或「AI 导入」开始积累"
        :image-size="80"
      />
    </el-card>

    <!-- AI 解析导入 -->
    <el-dialog v-model="importVisible" title="AI 解析导入" width="760px">
      <template v-if="!parsedList">
        <p class="import-hint">
          粘贴笔试题目文本（可含题干、选项、答案、解析），AI 会自动提取选择题。支持任意格式，一次可解析多题。
        </p>
        <el-input
          v-model="rawText"
          type="textarea"
          :rows="12"
          placeholder="粘贴题目文本，例如：&#10;1. 下列哪个是 JVM 的垃圾回收算法？&#10;A. 标记清除 B. 冒泡排序&#10;答案：A&#10;解析：……"
        />
      </template>
      <template v-else>
        <div class="parsed-head">
          <span>解析出 <b>{{ parsedList.length }}</b> 道题，勾选要导入的题目</span>
          <el-checkbox v-model="checkAll" @change="toggleAll">全选</el-checkbox>
        </div>
        <div class="parsed-list">
          <div v-for="(q, i) in parsedList" :key="i" class="parsed-row">
            <el-checkbox v-model="picked[i]" />
            <div class="parsed-body">
              <div class="parsed-q">{{ i + 1 }}. {{ q.question }}</div>
              <div class="parsed-options">
                {{ q.options.map((o, j) => letter(j) + '. ' + o).join('　') }}
              </div>
              <div class="parsed-meta">
                <el-tag size="small" :type="q.qtype === 'multi' ? 'warning' : 'primary'" effect="plain">
                  {{ q.qtype === 'multi' ? '多选' : '单选' }}
                </el-tag>
                <span class="parsed-answer">答案 {{ q.answer.map(letter).join('、') }}</span>
                <span v-if="q.analysis" class="parsed-analysis">解析：{{ q.analysis.slice(0, 60) }}{{ q.analysis.length > 40 ? '…' : '' }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
      <template #footer>
        <template v-if="!parsedList">
          <el-button @click="importVisible = false">取消</el-button>
          <el-button type="primary" :loading="parsing" :disabled="!rawText.trim()" @click="doParse">
            AI 解析
          </el-button>
        </template>
        <template v-else>
          <el-button @click="parsedList = null">重新粘贴</el-button>
          <el-button type="primary" :loading="importing" :disabled="pickedCount === 0" @click="doImport">
            导入 {{ pickedCount }} 题
          </el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useQuizStore } from '../store'
import * as api from '../api'
import type { ParsedQuiz } from '../types'

const route = useRoute()
const router = useRouter()
const store = useQuizStore()

/** 当前分类来自路由参数（分类为用户自建实体） */
const categoryId = computed(() => Number(route.params.id))
const categoryName = computed(
  () => store.categories.find((c) => c.id === categoryId.value)?.name ?? '分类',
)

onMounted(() => store.ensureLoaded())

const keyword = ref('')
const filterType = ref('')

const PAGE_SIZE = 5
const page = ref(store.listPage)

watch(page, (v) => {
  store.listPage = v
})

const filtered = computed(() => {
  let list = store.items.filter((i) => i.categoryId === categoryId.value)
  if (keyword.value) {
    const k = keyword.value.toLowerCase()
    list = list.filter(
      (i) =>
        i.question.toLowerCase().includes(k) ||
        i.options.some((o) => o.toLowerCase().includes(k)) ||
        (i.analysis ?? '').toLowerCase().includes(k),
    )
  }
  if (filterType.value) list = list.filter((i) => i.qtype === filterType.value)
  return list
})

const paged = computed(() =>
  filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE),
)

const singleCount = computed(
  () => store.items.filter((i) => i.categoryId === categoryId.value && i.qtype === 'single').length,
)
const multiCount = computed(
  () => store.items.filter((i) => i.categoryId === categoryId.value && i.qtype === 'multi').length,
)

// 搜索 / 筛选变化回第一页；数据变化后页码夹紧
watch([keyword, filterType], () => {
  page.value = 1
})
watch(filtered, (list) => {
  const maxPage = Math.max(1, Math.ceil(list.length / PAGE_SIZE))
  if (page.value > maxPage) page.value = maxPage
})

// 切换分类时重置视图状态
watch(
  () => route.params.id,
  () => {
    keyword.value = ''
    filterType.value = ''
    page.value = 1
  },
)

function letter(i: number): string {
  return String.fromCharCode(65 + i)
}

function answerText(item: { answer: number[] }): string {
  return item.answer.map(letter).join('、')
}

function goDetail(item: { categoryId: number; id: number }) {
  router.push(`/quiz/cat/${item.categoryId}/${item.id}`)
}

function goCreate() {
  router.push(`/quiz/cat/${categoryId.value}/new`)
}

// ---------- AI 解析导入 ----------
const importVisible = ref(false)
const rawText = ref('')
const parsing = ref(false)
const importing = ref(false)
const parsedList = ref<ParsedQuiz[] | null>(null)
const picked = ref<boolean[]>([])
const checkAll = ref(true)

function openAiImport() {
  rawText.value = ''
  parsedList.value = null
  importVisible.value = true
}

async function doParse() {
  parsing.value = true
  try {
    const { questions } = await api.parseQuiz(rawText.value)
    parsedList.value = questions
    picked.value = questions.map(() => true)
  } finally {
    parsing.value = false
  }
}

function toggleAll(v: boolean | string | number) {
  picked.value = parsedList.value?.map(() => !!v) ?? []
}

const pickedCount = computed(() => picked.value.filter(Boolean).length)

async function doImport() {
  const chosen = parsedList.value!.filter((_, i) => picked.value[i])
  importing.value = true
  try {
    await store.importParsed(categoryId.value, chosen)
    importVisible.value = false
  } finally {
    importing.value = false
  }
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

.count {
  font-size: 12.5px;
  color: var(--ink-3);
  white-space: nowrap;
}

.list-card :deep(.el-card__body) {
  padding: 12px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  /* 固定 5 条容量：不足一页时也占位，分页条位置不随条数漂移 */
  min-height: calc(84px * 5 + 8px * 4);
}

.quiz-card {
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  min-height: 84px;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.quiz-card:hover {
  border-color: #d8dbe0;
  background: #fafbfc;
}

.quiz-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.type-tag {
  flex-shrink: 0;
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

.answer {
  color: var(--el-color-primary);
  font-size: 12.5px;
  font-weight: 600;
  flex-shrink: 0;
}

.quiz-meta {
  margin-top: 8px;
  padding-left: 2px;
  display: flex;
  align-items: center;
  min-height: 20px;
  overflow: hidden;
  white-space: nowrap;
}

.options-preview {
  color: var(--ink-2);
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
}

/* AI 导入对话框 */
.import-hint {
  margin: 0 0 10px;
  font-size: 12.5px;
  color: var(--ink-3);
}

.parsed-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--ink-2);
}

.parsed-list {
  max-height: 52vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.parsed-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 10px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
}

.parsed-body {
  flex: 1;
  min-width: 0;
}

.parsed-q {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.parsed-options {
  margin-top: 3px;
  font-size: 12px;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.parsed-meta {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.parsed-answer {
  font-size: 12px;
  color: var(--el-color-primary);
  font-weight: 600;
}

.parsed-analysis {
  font-size: 12px;
  color: var(--ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>