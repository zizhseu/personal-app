<template>
  <div class="page">
    <el-page-header class="header" @back="goBack">
      <template #content>
        <div class="head-line">
          <span class="cat-tag">{{ catName }}</span>
          <el-tag size="small" :type="item?.qtype === 'multi' ? 'warning' : 'primary'" effect="plain" v-if="item">
            {{ item.qtype === 'multi' ? '多选' : '单选' }}
          </el-tag>
          <span class="head-hint">{{ modeLabel }}</span>
        </div>
      </template>
    </el-page-header>

    <template v-if="item || isNew">
      <!-- 编辑态：页面内直接填写 -->
      <el-card v-if="editing" shadow="never" class="block-card">
        <div class="form-label">题型</div>
        <el-radio-group v-model="draft.qtype">
          <el-radio value="single">单选</el-radio>
          <el-radio value="multi">多选</el-radio>
        </el-radio-group>

        <div class="form-label margin-top">题干</div>
        <el-input v-model="draft.question" type="textarea" :rows="3" placeholder="题目描述" />

        <div class="form-label margin-top">选项（点击左侧圆圈 / 方框勾选正确答案{{ draft.qtype === 'multi' ? '，可多选' : '' }}）</div>
        <div class="option-edit-list">
          <div v-for="(opt, i) in draft.options" :key="i" class="option-edit-row">
            <input
              :type="draft.qtype === 'multi' ? 'checkbox' : 'radio'"
              :name="'correct'"
              :checked="draft.answer.includes(i)"
              @change="toggleCorrect(i)"
            />
            <span class="opt-letter">{{ letter(i) }}.</span>
            <el-input v-model="draft.options[i]" placeholder="选项内容" />
            <el-icon class="opt-remove" title="删除该选项" @click="removeOption(i)">
              <Close />
            </el-icon>
          </div>
        </div>
        <el-button
          size="small"
          plain
          icon="Plus"
          :disabled="draft.options.length >= 8"
          @click="addOption"
        >
          添加选项（{{ draft.options.length }}/8）
        </el-button>

        <div class="form-label margin-top">解析（可选）</div>
        <el-input v-model="draft.analysis" type="textarea" :rows="4" placeholder="答案解析 / 知识点说明" />

        <div class="edit-actions">
          <el-button @click="cancelEdit">取消</el-button>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </div>
      </el-card>

      <!-- 查看态：问题区 / 答案区 / 解析区 -->
      <template v-else>
        <!-- 问题区 -->
        <el-card shadow="never" class="block-card">
          <div class="q-block">
            <span class="mark q">Q</span>
            <div class="q-text">{{ item!.question }}</div>
          </div>
          <div class="option-list">
            <label
              v-for="(opt, i) in item!.options"
              :key="i"
              class="option-row"
              :class="{
                correct: revealed && item!.answer.includes(i),
                wrong: revealed && pickedWrong(i),
                disabled: optionDisabled,
              }"
            >
              <input
                :type="item!.qtype === 'multi' ? 'checkbox' : 'radio'"
                :name="'quiz-' + item!.id"
                :checked="picks.includes(i)"
                :disabled="revealed || !interactive"
                @change="togglePick(i)"
              />
              <span class="opt-letter">{{ letter(i) }}.</span>
              <span class="opt-text">{{ opt }}</span>
              <el-icon v-if="revealed && item!.answer.includes(i)" class="opt-mark correct"><Check /></el-icon>
              <el-icon v-else-if="revealed && picks.includes(i) && !item!.answer.includes(i)" class="opt-mark wrong">
                <Close />
              </el-icon>
            </label>
          </div>
          <!-- 交互按钮（按显示时机） -->
          <div v-if="needAnswerButton" class="answer-actions">
            <el-button type="primary" :disabled="picks.length === 0" @click="submitAnswer">提交答案</el-button>
          </div>
          <div v-else-if="needRevealButton" class="answer-actions">
            <el-button plain @click="manualReveal">查看答案</el-button>
          </div>
        </el-card>

        <!-- 答案区 -->
        <el-card v-if="revealed" shadow="never" class="block-card">
          <div class="section-head">
            <span class="section-title">答案</span>
            <el-tag v-if="judged !== null" :type="judged ? 'success' : 'danger'" effect="dark" size="small">
              {{ judged ? '回答正确' : '回答错误' }}
            </el-tag>
          </div>
          <div class="answer-line">
            正确答案：
            <span class="answer-letters">{{ item!.answer.map(letter).join('、') }}</span>
            <template v-if="revealedByAnswer && picks.length">
              <span class="answer-sep">·</span>
              我的作答：<span class="my-letters">{{ picks.map(letter).join('、') || '未作答' }}</span>
            </template>
          </div>
          <div v-if="!item!.analysis" class="analysis-empty">（暂无解析）</div>
        </el-card>

        <!-- 解析区 -->
        <el-card v-if="revealed && item!.analysis" shadow="never" class="block-card">
          <div class="section-head">
            <span class="section-title">解析</span>
          </div>
          <div class="analysis-text">{{ item!.analysis }}</div>
        </el-card>

        <!-- 元信息行 -->
        <el-card shadow="never" class="block-card">
          <div class="meta-row">
            <el-button size="small" icon="ArrowLeft" :disabled="!prevItem" @click="goItem(prevItem)">
              上一个
            </el-button>
            <el-button size="small" :disabled="!nextItem" @click="goItem(nextItem)">
              下一个
              <el-icon class="btn-icon-right"><ArrowRight /></el-icon>
            </el-button>
            <span class="meta">创建于 {{ formatDateTime(item!.createdAt) }}</span>
            <span class="spacer" />
            <el-button type="danger" plain icon="Delete" @click="confirmRemove">删除</el-button>
            <el-button type="primary" icon="EditPen" @click="startEdit">编辑</el-button>
          </div>
        </el-card>
      </template>
    </template>
    <el-card v-else shadow="never" class="block-card">
      <el-skeleton :rows="5" animated />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Check, Close } from '@element-plus/icons-vue'
import { useQuizStore } from '../store'
import { useSettingsStore } from '@/modules/settings/store'
import type { QuizItem } from '../types'
import { formatDateTime } from '@/shared/utils/format'

const route = useRoute()
const router = useRouter()
const store = useQuizStore()
const settings = useSettingsStore()

/** 路由：/quiz/cat/:id(分类) + /:itemId(题目) 或 /new */
const isNew = computed(() => route.name === 'quiz-new')
const routeCategoryId = computed(() => Number(route.params.id))
const item = computed(
  () => store.items.find((i) => i.id === Number(route.params.itemId)) ?? null,
)
const currentCatId = computed(() => item.value?.categoryId ?? routeCategoryId.value)
const catName = computed(
  () => store.categories.find((c) => c.id === currentCatId.value)?.name ?? '分类',
)

const editing = ref(isNew.value)
const saving = ref(false)

onMounted(() => store.ensureLoaded())
const draft = reactive({
  question: '',
  options: [] as string[],
  answer: [] as number[],
  qtype: 'single' as 'single' | 'multi',
  analysis: '',
})

// ---------- 作答状态 ----------
/** 用户选择的选项下标 */
const picks = ref<number[]>([])
/** 答案区/解析区是否已显示 */
const revealed = ref(false)
/** manual 模式直接查看（非作答判定） */
const revealedByAnswer = ref(false)

const answerMode = computed(() => settings.quizAnswerMode)

/** 是否需要「提交答案」按钮（作答后显示模式） */
const needAnswerButton = computed(
  () => !revealed.value && answerMode.value === 'afterAnswer',
)
/** 是否显示「查看答案」按钮（手动模式） */
const needRevealButton = computed(
  () => !revealed.value && answerMode.value === 'manual',
)

/** 作答判定结果（null = 未判定） */
const judged = computed(() => {
  if (!revealedByAnswer.value || !item.value) return null
  const correct = item.value.answer
  const mine = picks.value
  return (
    mine.length === correct.length && mine.every((i) => correct.includes(i))
  )
})

/** 某选项是否被用户选错（判定显示用） */
function pickedWrong(i: number): boolean {
  return picks.value.includes(i) && !item.value!.answer.includes(i)
}

/** 选项是否可交互：未判定且非手动查看模式 */
const interactive = computed(
  () => !revealed.value && answerMode.value !== 'manual',
)

/** 选项行禁用视觉状态 */
const optionDisabled = computed(() => !interactive.value)

function toggleCorrect(i: number) {
  if (draft.qtype === 'single') draft.answer = [i]
  else {
    draft.answer = draft.answer.includes(i)
      ? draft.answer.filter((x) => x !== i)
      : [...draft.answer, i]
  }
}

function toggleOption(i: number) {
  if (item.value!.qtype === 'single') picks.value = [i]
  else picks.value = picks.value.includes(i) ? picks.value.filter((x) => x !== i) : [...picks.value, i]
}

/** instant 模式：点击选项即判定 */
function toggleAnswerPick(i: number) {
  toggleOption(i)
  revealed.value = true
  revealedByAnswer.value = true
}

function togglePick(i: number) {
  if (answerMode.value === 'instant') toggleAnswerPick(i)
  else toggleOption(i)
}

function submitAnswer() {
  revealed.value = true
  revealedByAnswer.value = true
}

function manualReveal() {
  revealed.value = true
  revealedByAnswer.value = false
}

const modeLabel = computed(() =>
  editing.value
    ? isNew.value
      ? '填写题干、选项与答案，保存后进入详情'
      : '编辑中，页面内修改后保存'
    : '',
)

// 切换题目时重置作答状态
watch(
  () => [item.value?.id, route.fullPath] as const,
  () => {
    editing.value = isNew.value
    picks.value = []
    revealed.value = answerMode.value === 'instant'
    revealedByAnswer.value = false
  },
)

// 显示时机变化时同步
watch(answerMode, (m) => {
  if (item.value && !isNew.value) {
    revealed.value = m === 'instant'
  }
})

function goBack() {
  router.push(`/quiz/cat/${currentCatId.value}`)
}

function startEdit() {
  draft.question = item.value!.question
  draft.options = [...item.value!.options]
  draft.answer = [...item.value!.answer]
  draft.qtype = item.value!.qtype
  draft.analysis = item.value!.analysis ?? ''
  editing.value = true
}

function cancelEdit() {
  if (isNew.value) goBack()
  else editing.value = false
}

function addOption() {
  draft.options.push('')
}

function removeOption(i: number) {
  if (draft.options.length <= 2) {
    ElMessage.warning('至少保留 2 个选项')
    return
  }
  draft.options.splice(i, 1)
  draft.answer = draft.answer
    .filter((x) => x !== i)
    .map((x) => (x > i ? x - 1 : x))
}

async function save() {
  const valid = draft.answer.filter((i) => i < draft.options.length)
  if (!draft.question.trim()) {
    ElMessage.warning('请填写题干')
    return
  }
  if (draft.options.filter((o) => o.trim()).length < 2) {
    ElMessage.warning('至少填写 2 个选项')
    return
  }
  if (!valid.length) {
    ElMessage.warning('请勾选正确答案')
    return
  }
  if (draft.qtype === 'multi' && valid.length < 2) {
    ElMessage.warning('多选题至少勾选 2 个正确答案')
    return
  }
  saving.value = true
  try {
    const payload = {
      question: draft.question.trim(),
      options: draft.options.map((o) => o.trim()),
      answer: valid,
      qtype: draft.qtype,
      analysis: draft.analysis.trim() || null,
    }
    if (isNew.value) {
      const created = await store.create({ categoryId: routeCategoryId.value, ...payload })
      await router.replace(`/quiz/cat/${routeCategoryId.value}/${created.id}`)
    } else {
      await store.update(item.value!.id, payload)
      editing.value = false
    }
  } finally {
    saving.value = false
  }
}

/** 同分类内的上一题 / 下一题 */
const categoryItems = computed(() =>
  store.items.filter((i) => i.categoryId === item.value?.categoryId),
)

const prevItem = computed(() => {
  if (!item.value) return null
  const idx = categoryItems.value.findIndex((i) => i.id === item.value!.id)
  return idx > 0 ? categoryItems.value[idx - 1] ?? null : null
})

const nextItem = computed(() => {
  if (!item.value) return null
  const idx = categoryItems.value.findIndex((i) => i.id === item.value!.id)
  return idx >= 0 && idx < categoryItems.value.length - 1
    ? categoryItems.value[idx + 1] ?? null
    : null
})

function goItem(target: QuizItem | null) {
  if (target) router.push(`/quiz/cat/${target.categoryId}/${target.id}`)
}

async function confirmRemove() {
  const it = item.value!
  const ok = await ElMessageBox.confirm(`确定删除这道题目吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (ok) {
    await store.remove(it.id)
    router.push(`/quiz/cat/${it.categoryId}`)
  }
}

// ---------- 作答事件 ----------
function letter(i: number): string {
  return String.fromCharCode(65 + i)
}
</script>
<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 960px;
}

.header {
  padding: 4px 0;
}

.head-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cat-tag {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
}

.head-hint {
  font-size: 12px;
  color: var(--ink-3);
  font-weight: 400;
}

.block-card {
  border-radius: var(--radius-card);
}

/* 问题区 */
.q-block {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  min-height: 48px;
}

.mark {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 8px;
  font-weight: 700;
  font-size: 15px;
  display: grid;
  place-items: center;
}

.mark.q {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.q-text {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.6;
  color: var(--ink);
  white-space: pre-wrap;
}

/* 选项列表 */
.option-list {
  margin-top: 14px;
  padding-left: 42px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.option-row:hover {
  background: #fafbfc;
}

.option-row.disabled {
  cursor: default;
}

.option-row.disabled:hover {
  background: transparent;
}

.option-row input {
  accent-color: var(--el-color-primary);
  flex-shrink: 0;
}

.option-row.correct {
  border-color: #22c55e;
  background: #f0fdf4;
}

.option-row.wrong {
  border-color: #ef4444;
  background: #fef2f2;
}

.opt-letter {
  font-weight: 700;
  color: var(--ink-2);
  flex-shrink: 0;
}

.opt-text {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  color: var(--ink);
}

.opt-mark {
  flex-shrink: 0;
  font-size: 14px;
}

.opt-mark.correct {
  color: #16a34a;
}

.opt-mark.wrong {
  color: #dc2626;
}

.answer-actions {
  margin-top: 14px;
  padding-left: 42px;
}

/* 答案区 / 解析区 */
.section-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-3);
  letter-spacing: 0.04em;
}

.answer-line {
  font-size: 14px;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.answer-letters {
  font-weight: 700;
  color: var(--el-color-primary);
}

.answer-sep {
  color: var(--ink-3);
}

.my-letters {
  font-weight: 600;
  color: var(--ink-2);
}

.analysis-empty {
  font-size: 13px;
  color: var(--ink-3);
}

.analysis-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink-2);
  white-space: pre-wrap;
}

/* 元信息行 */
.meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.meta {
  font-size: 12.5px;
  color: var(--ink-3);
}

.spacer {
  flex: 1;
}

.btn-icon-right {
  margin-left: 4px;
}

/* 编辑态 */
.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  margin-bottom: 8px;
}

.form-label.margin-top {
  margin-top: 20px;
}

.option-edit-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.option-edit-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.option-edit-row input {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  cursor: pointer;
  accent-color: var(--el-color-primary);
}

.opt-letter {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-2);
  flex-shrink: 0;
}

.opt-remove {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--ink-3);
  cursor: pointer;
  padding: 3px;
  border-radius: 4px;
  transition: color 0.15s ease;
}

.opt-remove:hover {
  color: var(--el-color-danger);
  background: #f1f2f4;
}

.edit-actions {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 760px) {
  .head-line, .meta-row { flex-wrap: wrap; }
  .meta-row .el-button + .el-button { margin-left: 0; }
  .meta-row .spacer { display: none; }
  .q-text { min-width: 0; overflow-wrap: anywhere; }
  .option-list { padding-left: 0; }
}
</style>
