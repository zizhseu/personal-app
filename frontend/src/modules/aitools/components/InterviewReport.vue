<template>
  <div v-if="session.report" class="report">
    <el-card shadow="never">
      <template #header><span class="section-title">本次复盘</span></template>
      <p class="summary">{{ session.report.summary }}</p>
      <div class="summary-grid">
        <section v-if="session.report.strengths.length">
          <h3>已表现出的优势</h3>
          <ul><li v-for="text in session.report.strengths" :key="text">{{ text }}</li></ul>
        </section>
        <section v-if="session.report.improvements.length">
          <h3>下一步练习重点</h3>
          <ul><li v-for="text in session.report.improvements" :key="text">{{ text }}</li></ul>
        </section>
      </div>
    </el-card>
    <el-card v-for="(item, index) in session.report.items" :key="item.answerMessageId" shadow="never">
      <div class="item-heading">
        <h3>{{ message(item.questionMessageId) }}</h3>
        <el-tag :type="item.assessment === 'solid' ? 'success' : item.assessment === 'partial' ? 'warning' : 'danger'" effect="plain">
          {{ assessmentLabels[item.assessment] }}
        </el-tag>
      </div>
      <blockquote v-if="item.resumeQuote" class="resume-quote">简历依据：{{ item.resumeQuote }}</blockquote>
      <p class="feedback">{{ item.feedback }}</p>
      <div class="guide">
        <h4>改进要点</h4>
        <div class="md-body" v-html="renderMarkdown(item.improvementGuide)" />
      </div>
      <div class="knowledge"><el-tag v-for="point in item.knowledgePoints" :key="point" size="small" type="info" effect="plain">{{ point }}</el-tag></div>
      <el-collapse class="source">
        <el-collapse-item title="查看原始回答" name="answer"><p class="original-answer">{{ message(item.answerMessageId) }}</p></el-collapse-item>
      </el-collapse>
      <div class="item-actions">
        <el-button icon="Reading" :disabled="hasExport(index, 'qa')" @click="openExport(index, 'qa')">{{ hasExport(index, 'qa') ? '已加入问答' : '加入问答' }}</el-button>
        <el-button icon="List" :disabled="hasExport(index, 'todo')" @click="openExport(index, 'todo')">{{ hasExport(index, 'todo') ? '已加入待办' : '加入待办' }}</el-button>
      </div>
    </el-card>

    <el-dialog v-model="exportVisible" :title="exportKind === 'qa' ? '确认加入问答' : '确认加入待办'" width="760px" :close-on-click-modal="false" :show-close="!saving">
      <el-form label-position="top" @submit.prevent="confirmExport">
        <el-form-item :label="exportKind === 'qa' ? '问答分类' : '待办目录'">
          <el-select v-model="form.categoryId" placeholder="选择保存位置">
            <el-option v-for="category in categories" :key="category.id" :value="category.id" :label="category.name" />
          </el-select>
          <p v-if="!categories.length" class="hint">请先关闭弹窗，在左侧新建{{ exportKind === 'qa' ? '问答分类' : '待办目录' }}。</p>
        </el-form-item>
        <el-form-item :label="exportKind === 'qa' ? '问题' : '待办标题'"><el-input v-model="form.title" :maxlength="exportKind === 'qa' ? 500 : 200" show-word-limit /></el-form-item>
        <el-form-item :label="exportKind === 'qa' ? '练习要点与复盘记录' : '备注'"><el-input v-model="form.content" type="textarea" :rows="9" :maxlength="exportKind === 'qa' ? 20000 : 10000" show-word-limit /></el-form-item>
        <el-form-item v-if="exportKind === 'todo'" label="截止时间（选填）"><el-date-picker v-model="form.dueAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="不限时间" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="exportVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!form.categoryId || !form.title.trim()" @click="confirmExport">确认加入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useQaStore } from '@/modules/qa/store'
import { useTodoStore } from '@/modules/todo/store'
import { renderMarkdown } from '@/shared/utils/markdown'
import * as api from '../api'
import type { InterviewSession } from '../types'

const props = defineProps<{ session: InterviewSession }>()
const emit = defineEmits<{ changed: [sessionId: number] }>()
const qa = useQaStore()
const todo = useTodoStore()
const assessmentLabels = { solid: '回答较充分', partial: '仍可深入', needs_work: '需要加强' }
const exportVisible = ref(false)
const exportKind = ref<'qa' | 'todo'>('qa')
const exportIndex = ref(0)
const exportSessionId = ref(0)
const saving = ref(false)
const form = reactive({ categoryId: null as number | null, title: '', content: '', dueAt: null as string | null })
const categories = computed(() => exportKind.value === 'qa' ? qa.categories : todo.categories)
const message = (id: number) => props.session.messages.find((row) => row.id === id)?.content ?? ''
const hasExport = (index: number, kind: 'qa' | 'todo') => props.session.actions.some((action) => action.itemIndex === index && action.kind === kind && action.targetId !== null)

watch(() => props.session.id, () => { exportVisible.value = false })

async function openExport(index: number, kind: 'qa' | 'todo') {
  const sessionId = props.session.id
  try { await (kind === 'qa' ? qa.ensureLoaded() : todo.ensureLoaded()) } catch { return }
  if (sessionId !== props.session.id) return
  const item = props.session.report?.items[index]
  if (!item) return
  exportKind.value = kind
  exportIndex.value = index
  exportSessionId.value = sessionId
  form.categoryId = (kind === 'qa' ? qa.categories : todo.categories)[0]?.id ?? null
  form.title = message(item.questionMessageId).slice(0, kind === 'qa' ? 500 : 200)
  form.content = `## 练习要点\n${item.improvementGuide}\n\n## 本次反馈\n${item.feedback}\n\n来源：[${props.session.resumeName} · 面试复盘](/aitools/interview?session=${sessionId})`
  form.dueAt = null
  exportVisible.value = true
}

async function confirmExport() {
  if (saving.value || !form.categoryId || !form.title.trim()) return
  saving.value = true
  try {
    await api.exportReview(exportSessionId.value, { itemIndex: exportIndex.value, kind: exportKind.value, categoryId: form.categoryId, title: form.title.trim(), content: form.content, dueAt: form.dueAt })
    exportVisible.value = false
    emit('changed', exportSessionId.value)
    await (exportKind.value === 'qa' ? qa.loadAll() : todo.loadAll())
    ElMessage.success(exportKind.value === 'qa' ? '已加入问答' : '已加入待办')
  } catch { /* 保留预览，允许重试；服务端防止重复导入。 */ }
  finally { saving.value = false }
}
</script>

<style scoped>
.report { display: flex; flex-direction: column; gap: 16px; min-width: 0; overflow-wrap: anywhere; }
.section-title { font-weight: 650; }
.summary { margin: 0; color: var(--ink); line-height: 1.8; }
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; margin-top: 18px; }
.summary-grid h3, .guide h4 { margin: 0 0 8px; font-size: 13px; color: var(--ink-2); }
.summary-grid ul { margin: 0; padding-left: 18px; color: var(--ink-2); font-size: 13px; line-height: 1.8; }
.item-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }
.item-heading h3 { margin: 0; font-size: 16px; line-height: 1.7; overflow-wrap: anywhere; }
.item-heading .el-tag { flex-shrink: 0; margin-top: 3px; }
.resume-quote { margin: 16px 0; padding: 10px 14px; border-left: 3px solid var(--accent); background: var(--surface-sunken); color: var(--ink-2); font-size: 13px; line-height: 1.8; white-space: pre-wrap; }
.feedback { color: var(--ink-2); font-size: 14px; line-height: 1.8; }
.guide { margin-top: 16px; }
.knowledge, .item-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.knowledge .el-tag { max-width: 100%; }
.knowledge :deep(.el-tag__content) { overflow: hidden; text-overflow: ellipsis; }
.item-actions .el-button + .el-button { margin-left: 0; }
.source { margin-top: 16px; border: 0; }
.source :deep(.el-collapse-item__header) { color: var(--ink-3); }
.original-answer { margin: 0; white-space: pre-wrap; color: var(--ink-2); line-height: 1.8; }
.hint { color: var(--ink-3); font-size: 12px; }
@media (max-width: 760px) { .summary-grid { grid-template-columns: 1fr; gap: 16px; } .item-heading { flex-wrap: wrap; gap: 8px; } }
</style>
