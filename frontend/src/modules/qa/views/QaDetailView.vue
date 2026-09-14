<template>
  <div class="page">
    <el-page-header class="header" @back="goBack">
      <template #content>
        <div class="head-line">
          <span class="cat-tag">{{ catName }}</span>
          <span class="head-hint">{{ modeLabel }}</span>
        </div>
      </template>
    </el-page-header>

    <template v-if="item || isNew">
      <!-- 编辑态：页面内直接填写 -->
      <el-card v-if="editing" shadow="never" class="block-card">
        <div class="form-label">问题</div>
        <el-input v-model="draft.question" placeholder="面试问题 / 考点" size="large" />
        <div class="form-label margin-top">答案要点（支持 Markdown：## 标题、- 列表、**加粗**、代码块）</div>
        <el-input
          v-model="draft.answer"
          type="textarea"
          :rows="16"
          placeholder="## 考点&#10;- 要点一&#10;- 要点二&#10;&#10;\`\`\`sql&#10;SELECT ...&#10;\`\`\`"
        />
        <div class="edit-actions">
          <el-button @click="cancelEdit">取消</el-button>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </div>
      </el-card>

      <!-- 查看态 -->
      <template v-else>
        <el-card shadow="never" class="block-card">
          <div class="q-block">
            <span class="mark q">Q</span>
            <div class="q-text md-body" v-html="renderMarkdown(item!.question)"></div>
          </div>
          <div class="divider" />
          <div class="a-block">
            <span class="mark a">A</span>
            <div
              v-if="item!.answer"
              class="a-scroll md-body"
              v-html="renderMarkdown(item.answer)"
            ></div>
            <div v-else class="a-scroll empty">（暂无答案，点击右上角「编辑」补充）</div>
          </div>
        </el-card>

        <el-card shadow="never" class="block-card">
          <div class="meta-row">
            <el-button size="small" icon="ArrowLeft" :disabled="!prevItem" @click="goItem(prevItem)">
              上一个
            </el-button>
            <el-button size="small" :disabled="!nextItem" @click="goItem(nextItem)">
              下一个
              <el-icon class="btn-icon-right"><ArrowRight /></el-icon>
            </el-button>
            <el-tag
              class="status-tag"
              :color="QA_STATUS_COLORS[item!.status]"
              effect="dark"
              title="点击切换掌握状态"
              @click="toggleStatus"
            >
              {{ QA_STATUS_LABELS[item!.status] }}
            </el-tag>
            <span class="meta">创建于 {{ formatDateTime(item!.createdAt) }}</span>
            <span class="meta">更新于 {{ formatDateTime(item!.updatedAt) }}</span>
            <span class="spacer" />
            <el-button type="danger" plain icon="Delete" @click="confirmRemove">删除</el-button>
            <el-button type="primary" icon="EditPen" @click="startEdit">编辑</el-button>
          </div>
          <div class="tags-row">
            <span class="tags-label">标签</span>
            <span class="tags-wrap">
              <template v-if="item!.tags?.length">
                <el-tag v-for="t in item!.tags" :key="t" size="small" effect="plain" class="mini-tag">
                  {{ t }}
                </el-tag>
              </template>
              <span v-else class="tags-empty">无标签</span>
            </span>
            <!-- 点击 + 直接打标签：勾选当前分类已有 / 输入新建 -->
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
              <el-checkbox-group v-model="itemTags" @change="saveTags">
                <div class="tag-pick-list">
                  <el-checkbox v-for="t in allTags" :key="t" :value="t">{{ t }}</el-checkbox>
                </div>
              </el-checkbox-group>
              <div class="tag-add">
                <el-input
                  v-model="newTag"
                  size="small"
                  placeholder="新标签，回车添加"
                  @keyup.enter="addTag"
                />
                <el-button size="small" type="primary" plain @click="addTag">添加</el-button>
              </div>
            </el-popover>
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
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import { QA_STATUS_LABELS, QA_STATUS_COLORS } from '../constants'
import { useQaStore } from '../store'
import type { QaItem } from '../types'
import { formatDateTime } from '@/shared/utils/format'
import { renderMarkdown } from '@/shared/utils/markdown'

const route = useRoute()
const router = useRouter()
const store = useQaStore()

/** 路由：/qa/cat/:id(分类) + /:itemId(题目) 或 /new */
const isNew = computed(() => route.name === 'qa-new')
const routeCategoryId = computed(() => Number(route.params.id))
const item = computed(
  () => store.items.find((i) => i.id === Number(route.params.itemId)) ?? null,
)
const currentCatId = computed(() => item.value?.categoryId ?? routeCategoryId.value)
const catName = computed(
  () => store.categories.find((c) => c.id === currentCatId.value)?.name ?? '分类',
)

const editing = ref(isNew.value)
const draft = reactive({ question: '', answer: '' })
const saving = ref(false)

/** 标签（查看态浮层直接编辑，双向代理到当前题目） */
const newTag = ref('')
const itemTags = computed({
  get: () => item.value?.tags ?? [],
  set: (v) => {
    if (item.value) item.value.tags = v
  },
})

async function saveTags() {
  if (!item.value) return
  await store.update(item.value.id, { tags: itemTags.value }, true)
}

function addTag() {
  const tag = newTag.value.trim()
  if (!tag) return
  if (!itemTags.value.includes(tag)) {
    itemTags.value = [...itemTags.value, tag]
    void saveTags()
  }
  newTag.value = ''
}

// 路由变化时重置编辑状态（详情间切换 / 新建 → 详情）
watch(
  () => route.fullPath,
  () => {
    editing.value = isNew.value
  },
)

/** 标签候选 = 当前分类出现过的标签 + 该题已有标签（编辑下拉候选） */
const allTags = computed(() => {
  const fromCat = store.items
    .filter((i) => i.categoryId === currentCatId.value)
    .flatMap((i) => i.tags ?? [])
  return [...new Set([...fromCat, ...(item.value?.tags ?? [])])].sort((a, b) =>
    a.localeCompare(b, 'zh'),
  )
})

// 进入某题详情即视为阅读，更新最后阅读时间
// immediate：从索引点进详情时 id 一开始就有值（无"变化"），必须立即执行一次
watch(
  () => item.value?.id,
  (id, old) => {
    if (id && id !== old) void store.markRead(id)
  },
  { immediate: true },
)

const modeLabel = computed(() =>
  editing.value ? (isNew.value ? '填写问题与答案要点，保存后进入详情' : '编辑中，页面内修改后保存') : '点击标签切换掌握状态',
)

function goBack() {
  router.push(`/qa/cat/${currentCatId.value}`)
}

function startEdit() {
  draft.question = item.value!.question
  draft.answer = item.value!.answer ?? ''
  editing.value = true
}

function cancelEdit() {
  if (isNew.value) goBack()
  else editing.value = false
}

async function save() {
  if (!draft.question.trim()) {
    ElMessage.warning('请填写问题')
    return
  }
  saving.value = true
  try {
    // 标签走查看态浮层独立保存，此处只更新问题与答案
    const payload = {
      question: draft.question.trim(),
      answer: draft.answer.trim() || null,
    }
    if (isNew.value) {
      const created = await store.create({ categoryId: routeCategoryId.value, ...payload })
      await router.replace(`/qa/cat/${routeCategoryId.value}/${created.id}`)
    } else {
      await store.update(item.value!.id, payload)
      editing.value = false
    }
  } finally {
    saving.value = false
  }
}

function toggleStatus() {
  if (!item.value) return
  void store.patchStatus(item.value.id, item.value.status === 'mastered' ? 'learning' : 'mastered')
}

/** 同分类内的上一题 / 下一题（顺序 = 索引页顺序） */
const categoryItems = computed(() =>
  store.items.filter((i) => i.categoryId === item.value?.categoryId),
)

const prevItem = computed(() => {
  if (!item.value) return null
  const idx = categoryItems.value.findIndex((i) => i.id === item.value!.id)
  return idx > 0 ? categoryItems.value[idx - 1] : null
})

const nextItem = computed(() => {
  if (!item.value) return null
  const idx = categoryItems.value.findIndex((i) => i.id === item.value!.id)
  return idx >= 0 && idx < categoryItems.value.length - 1
    ? categoryItems.value[idx + 1]
    : null
})

function goItem(target: QaItem | null) {
  if (target) router.push(`/qa/cat/${target.categoryId}/${target.id}`)
}

async function confirmRemove() {
  const it = item.value!
  const ok = await ElMessageBox.confirm(`确定删除「${it.question}」吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (ok) {
    await store.remove(it.id)
    router.push(`/qa/cat/${it.categoryId}`)
  }
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 860px;
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

/* Q / A 区块：高度锁定，上一个/下一个按钮位置恒定 */
.q-block,
.a-block {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.q-block {
  min-height: 56px; /* 两行问题容量 */
}

.divider {
  height: 1px;
  background: var(--line-soft);
  margin: 16px 0;
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

.mark.a {
  background: #f2f2f3;
  color: var(--ink-2);
}

.q-text {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.5;
  color: var(--ink);
}

.a-scroll {
  flex: 1;
  min-width: 0;
  /* 固定高度：内容少也占满（按钮不漂移），内容多则容器内滚动 */
  height: calc(100vh - 400px);
  min-height: 220px;
  overflow-y: auto;
  padding-right: 12px;
}

.a-scroll.empty {
  color: var(--ink-3);
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

.edit-actions {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 元信息行 */
.meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn-icon-right {
  margin-left: 4px;
}

.status-tag {
  border: none;
  color: #fff;
  font-weight: 600;
  border-radius: 999px;
  cursor: pointer;
}

.meta {
  font-size: 12.5px;
  color: var(--ink-3);
}

.tags-row {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--line-soft);
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
}

.tags-label {
  font-size: 12.5px;
  color: var(--ink-3);
  flex-shrink: 0;
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

.tags-empty {
  font-size: 12.5px;
  color: var(--ink-3);
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

.mini-tag {
  color: var(--ink-2);
  background: #f2f2f3;
  border-color: transparent;
  flex-shrink: 0;
}

.spacer {
  flex: 1;
}
</style>