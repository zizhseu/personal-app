<template>
  <div v-loading="loading" class="page">
    <div class="page-head"><el-button text icon="ArrowLeft" @click="emit('back')">返回资料</el-button><div class="actions"><el-button icon="Refresh" :disabled="processing || dirty" @click="load">刷新</el-button><el-button type="danger" plain icon="Delete" :disabled="working" @click="remove">删除资料</el-button></div></div>
    <template v-if="note">
      <el-alert v-if="demoMode" title="当前为独立功能验证：示例面经与模拟 AI，不使用真实模型额度" type="info" :closable="false" />
      <div class="note-heading"><div><h1>{{ note.title }}</h1><p>{{ [note.author, note.platform === 'manual' ? '手动导入' : '小红书', note.publishedAt ? dayjs(note.publishedAt).format('YYYY-MM-DD') : ''].filter(Boolean).join(' · ') }}</p></div><a v-if="note.sourceUrl" :href="note.sourceUrl" target="_blank" rel="noopener noreferrer">查看原笔记 ↗</a></div>
      <el-card shadow="never" class="workflow-card"><div class="workflow-actions"><div><strong>先核对材料，再提取面试问题</strong><p class="hint">正文、图片识别文字和 AI 整理分别保存。每道题都需要通过原文引用校验。</p></div><div class="actions"><el-button icon="Picture" :loading="processing && activeWork === 'ocr'" :disabled="working || dirty || !remainingImages" @click="run('ocr')">{{ remainingImages ? `识别图片（剩余 ${remainingImages} 张）` : '图片已识别' }}</el-button><el-button type="primary" icon="MagicStick" :loading="processing && activeWork === 'analyze'" :disabled="working || dirty || !modelReady" @click="run('analyze')">AI 整理文字</el-button></div></div><p v-if="!modelReady" class="hint">尚未配置可用的大模型，请前往<router-link to="/settings">设置 · 大模型</router-link>配置。</p><p v-else-if="modelAuthMode === 'chatgpt'" class="hint">正在使用 ChatGPT 套餐 · {{ modelName }} <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noopener noreferrer">管理用量</a></p><p v-if="remainingImages" class="hint">还有 {{ remainingImages }} 张图片尚未识别成功；每次最多识别 6 张。AI 整理只覆盖已获取的文字。</p></el-card>
      <el-alert v-if="note.workStatus === 'pending'" type="info" :closable="false" show-icon :title="note.workKind === 'ocr' ? '正在识别图片，可以稍后从本地资料返回查看' : '正在整理面试问题，可以稍后从本地资料返回查看'" />
      <el-alert v-if="note.error" type="warning" :closable="false" show-icon :title="note.error" />
      <el-tabs v-model="activeTab"><el-tab-pane :label="`材料与校对 · ${note.imageCount} 张图片`" name="material" /><el-tab-pane :label="`AI 整理 · ${note.report?.questions.length ?? 0} 道题`" name="report" /></el-tabs>
      <template v-if="activeTab === 'material'">
        <el-card shadow="never"><div class="material-head"><div><strong>核对识别文字</strong><p class="hint">可修正识别错误。修改并保存后需重新整理，已加入问答的内容仍保留。</p></div><el-button type="primary" plain :loading="saving" :disabled="!dirty || working" @click="save">保存校对</el-button></div><el-collapse v-model="openSources"><el-collapse-item v-for="source in material" :id="`source-${source.id}`" :key="source.id" :name="source.id"><template #title><span>{{ source.label }}</span><el-tag v-if="source.text !== source.originalText" size="small" type="info" class="source-tag">已校对</el-tag></template><div class="source-grid" :class="{ 'with-image': source.id.startsWith('image-') }"><img v-if="sourceImage(source.id)" :src="sourceImage(source.id)" :alt="source.label" loading="lazy" referrerpolicy="no-referrer" /><div class="source-editor"><el-input v-model="source.text" type="textarea" :rows="source.id === 'title' ? 2 : 9" :disabled="working" :maxlength="60000" show-word-limit :aria-label="`${source.label}校对文字`" /><details v-if="source.text !== source.originalText"><summary>查看最初提取的文字</summary><pre>{{ source.originalText }}</pre></details></div></div></el-collapse-item></el-collapse></el-card>
        <el-card v-if="note.images.some(image => image.status !== 'done')" shadow="never"><h3>待识别图片</h3><div class="pending-images"><div v-for="(image, index) in note.images" :key="image.id" v-show="image.status !== 'done'" class="pending-image"><img v-if="image.url" :src="image.url" :alt="`图片 ${index + 1}`" loading="lazy" referrerpolicy="no-referrer" /><p>图片 {{ index + 1 }} · {{ image.status === 'failed' ? '未识别成功' : '待识别' }}</p><small v-if="image.error">{{ image.error }}</small></div></div><p class="hint">识别失败时可将图片中的文字补充到正文，保存校对后整理。OCR 可能存在错误，请结合原图核对。</p></el-card>
      </template>
      <template v-else-if="note.report">
        <el-card shadow="never"><div class="report-heading"><h3>面经摘要</h3><el-tag type="info" effect="plain">AI 整理，请核对</el-tag></div><p class="summary">{{ note.report.summary }}</p><div class="metadata"><el-tag v-for="value in [note.report.company, note.report.position, note.report.round].filter(Boolean)" :key="value!" effect="plain">{{ value }}</el-tag></div><p v-if="remainingImages" class="hint">当前摘要与题目未覆盖尚未识别成功的 {{ remainingImages }} 张图片。</p></el-card>
        <el-card v-for="(question, index) in note.report.questions" :key="`${note.reportId}-${index}`" shadow="never"><div class="question-head"><h3><span class="question-number">{{ String(index + 1).padStart(2, '0') }}</span>{{ question.question }}</h3><el-button type="primary" plain :disabled="exported(index)" @click="openExport(index)">{{ exported(index) ? '已加入问答' : '加入问答' }}</el-button></div><blockquote>{{ question.quote }}</blockquote><div class="question-footer"><div class="topics"><el-tag v-for="topic in question.topics" :key="topic" size="small" type="info">{{ topic }}</el-tag></div><el-button link type="primary" @click="showSource(question.sourceId)">查看{{ sourceLabel(question.sourceId) }}出处</el-button></div></el-card>
        <el-empty v-if="!note.report.questions.length" description="本次没有提取到面试问题，可先核对材料是否完整" :image-size="70" />
      </template>
      <el-empty v-else description="核对材料后，点击「AI 整理文字」提取面试问题" :image-size="80" />
    </template>
    <el-empty v-else-if="!loading" description="未能读取此资料，可返回本地资料重新打开" />
    <el-dialog v-model="exportOpen" title="确认加入问答" width="min(680px, calc(100vw - 32px))" :close-on-click-modal="false"><el-form label-position="top"><el-form-item label="问答分类"><el-select v-model="exportCategory" placeholder="选择分类"><el-option v-for="category in qa.categories" :key="category.id" :label="category.name" :value="category.id" /></el-select><p v-if="!qa.categories.length" class="hint">请先从侧边栏新增一个问答分类。</p></el-form-item><el-form-item label="问题"><el-input v-model="exportTitle" :maxlength="500" /></el-form-item><div class="export-source"><strong>会保留的来源片段</strong><p>{{ note?.report?.questions[exportIndex]?.quote }}</p><small>引文作为来源资料保存，不作为生成的标准答案。</small></div></el-form><template #footer><el-button @click="exportOpen = false">取消</el-button><el-button type="primary" :disabled="!exportCategory || !exportTitle.trim()" :loading="exporting" @click="confirmExport">确认加入</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { fetchStatus } from '@/modules/aitools/api'
import { useQaStore } from '@/modules/qa/store'
import * as api from '../api'
import type { ExperienceNote, MaterialSource } from '../types'
const props = defineProps<{ noteId: number }>()
const emit = defineEmits<{ back: []; deleted: [] }>()
const qa = useQaStore()
const note = ref<ExperienceNote | null>(null), material = ref<MaterialSource[]>([])
const loading = ref(true), processing = ref(false), saving = ref(false), activeWork = ref('')
const activeTab = ref('material'), openSources = ref(['body'])
const modelReady = ref(false), modelAuthMode = ref(''), modelName = ref(''), demoMode = ref(false)
const exportOpen = ref(false), exportIndex = ref(0), exportCategory = ref<number | null>(null), exportTitle = ref(''), exporting = ref(false)
const dirty = computed(() => !!note.value && JSON.stringify(material.value) !== JSON.stringify(note.value.sources))
const working = computed(() => processing.value || saving.value || note.value?.workStatus === 'pending')
const remainingImages = computed(() => note.value?.images.filter(image => image.status !== 'done').length ?? 0)
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false
function adopt(value: ExperienceNote) { if (disposed) return; note.value = value; material.value = structuredClone(value.sources); clearTimeout(timer); if (value.workStatus === 'pending') timer = setTimeout(poll, 3000) }
async function load() { loading.value = true; try { adopt(await api.fetchNote(props.noteId)) } catch { /* 保留已有内容。 */ } finally { loading.value = false } }
async function poll() { if (disposed) return; try { adopt(await api.fetchNote(props.noteId)) } catch { if (!disposed) timer = setTimeout(poll, 5000) } }
async function save() { if (!note.value) return; saving.value = true; try { adopt(await api.saveMaterial(props.noteId, note.value.revision, material.value)); ElMessage.success('校对材料已保存') } catch { /* 保留草稿供修正。 */ } finally { saving.value = false } }
async function run(kind: 'ocr' | 'analyze') { processing.value = true; activeWork.value = kind; try { const result = kind === 'ocr' ? await api.recognizeImages(props.noteId) : await api.analyzeNote(props.noteId); adopt(result); if (kind === 'analyze') activeTab.value = 'report'; else ElMessage.success('本次图片识别已保存，请核对文字并继续处理剩余图片') } catch { await load() } finally { processing.value = false } }
function sourceImage(id: string) { if (!note.value) return ''; const index = note.value.images.findIndex(image => image.id === id); if (index < 0) return ''; const image = note.value.images[index]!; return image.stored ? `/api/experiences/notes/${props.noteId}/images/${index}` : image.url }
const sourceLabel = (id: string) => note.value?.sources.find(source => source.id === id)?.label ?? '原文'
const exported = (index: number) => !!note.value?.actions.some(action => action.reportId === note.value?.reportId && action.itemIndex === index && action.qaId !== null)
async function showSource(id: string) { activeTab.value = 'material'; if (!openSources.value.includes(id)) openSources.value.push(id); await nextTick(); document.getElementById(`source-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }
async function openExport(index: number) { if (!note.value?.report) return; await qa.ensureLoaded(); exportIndex.value = index; exportTitle.value = note.value.report.questions[index]!.question; exportCategory.value ??= qa.categories[0]?.id ?? null; exportOpen.value = true }
async function confirmExport() { if (!note.value?.reportId || !exportCategory.value) return; exporting.value = true; try { const action = await api.exportQuestion(props.noteId, { reportId: note.value.reportId, itemIndex: exportIndex.value, categoryId: exportCategory.value, title: exportTitle.value }); note.value.actions = note.value.actions.filter(item => !(item.reportId === action.reportId && item.itemIndex === action.itemIndex)).concat(action); await qa.loadAll(); exportOpen.value = false; ElMessage.success('问题与来源已加入问答') } catch { /* 保留确认内容，重复提交不会重复入库。 */ } finally { exporting.value = false } }
async function remove() { try { await ElMessageBox.confirm('删除此面经及本机图片？已加入问答的题目会保留。', '删除面经', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }); await api.deleteNote(props.noteId); emit('deleted') } catch { /* 取消或失败时保留页面。 */ } }
onMounted(async () => { await load(); try { const status = await fetchStatus(); modelReady.value = status.llmReady; modelAuthMode.value = status.authMode ?? ''; modelName.value = status.model ?? ''; demoMode.value = status.demoMode === true } catch { /* 仍可查看和校对原始材料。 */ } })
onBeforeUnmount(() => { disposed = true; clearTimeout(timer) })
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.page-head, .actions, .note-heading, .workflow-actions, .material-head, .question-head, .question-footer, .report-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.actions { justify-content: flex-end; flex-wrap: wrap; }
.actions .el-button + .el-button { margin-left: 0; }
h1 { font-size: 22px; color: var(--ink); margin: 0; line-height: 1.6; }
.note-heading p { color: var(--ink-3); font-size: 12px; margin: 7px 0 0; }
.note-heading > div { min-width: 0; }
.note-heading > a { white-space: nowrap; }
h3 { color: var(--ink); margin: 0; font-size: 16px; line-height: 1.8; }
a { color: var(--accent); font-size: 13px; }
.hint { color: var(--ink-3); font-size: 12px; line-height: 1.8; margin: 8px 0 0; }
.hint a { margin: 0 5px; }
.el-card { border-radius: var(--radius-card); }
.material-head { margin-bottom: 18px; }
.source-tag { margin-left: 10px; }
.source-grid { display: grid; grid-template-columns: 1fr; gap: 22px; padding: 8px 0; }
.source-grid.with-image { grid-template-columns: minmax(180px, 0.65fr) minmax(0, 1.35fr); }
.source-grid img { width: 100%; max-height: 500px; object-fit: contain; background: var(--surface-sunken); border-radius: 8px; }
.source-editor { min-width: 0; }
.source-editor details { margin-top: 12px; color: var(--ink-3); font-size: 12px; }
.source-editor pre { white-space: pre-wrap; overflow-wrap: anywhere; }
.pending-images { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 18px; margin-top: 18px; }
.pending-image img { width: 100%; height: 190px; object-fit: contain; background: var(--surface-sunken); border-radius: 8px; }
.pending-image p, .pending-image small { font-size: 12px; color: var(--ink-3); line-height: 1.6; }
.summary { white-space: pre-wrap; line-height: 1.9; color: var(--ink-2); font-size: 14px; }
.metadata, .topics { display: flex; flex-wrap: wrap; gap: 8px; }
.question-head { align-items: flex-start; }
.question-head h3 { flex: 1; }
.question-number { color: var(--accent); font-size: 13px; margin-right: 12px; }
blockquote { margin: 18px 0; border-left: 3px solid var(--el-color-primary-light-5); background: var(--surface-sunken); color: var(--ink-2); white-space: pre-wrap; overflow-wrap: anywhere; padding: 14px 18px; line-height: 1.9; font-size: 13px; }
.export-source { padding: 16px; background: var(--surface-sunken); border-radius: 8px; white-space: pre-wrap; line-height: 1.8; }
.export-source small { color: var(--ink-3); }
@media (max-width: 900px) { .workflow-actions { align-items: flex-start; flex-direction: column; } }
@media (max-width: 600px) { .note-heading, .material-head { align-items: flex-start; flex-direction: column; } .source-grid.with-image { grid-template-columns: 1fr; } .question-head, .question-footer { flex-direction: column; align-items: flex-start; } h1 { font-size: 19px; } }
</style>
