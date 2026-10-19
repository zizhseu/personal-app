<template>
  <ExperienceDetail v-if="noteId" :key="noteId" :note-id="noteId" @back="back" @deleted="back" />
  <div v-else class="page">
    <div class="page-head"><div><h1>面经资料</h1><p class="sub">从真实面试经历中整理问题，保留原始材料与引用。</p></div><div class="actions"><el-button icon="Connection" @click="connectionOpen = true">{{ connected ? '小红书已连接' : '连接小红书' }}</el-button><el-button icon="DocumentAdd" @click="manualOpen = true">手动导入</el-button></div></div>
    <el-tabs v-model="tab"><el-tab-pane label="搜索获取" name="search" /><el-tab-pane :label="`本地资料 · ${notes.length}`" name="library" /></el-tabs>
    <template v-if="tab === 'search'">
      <el-card shadow="never" class="search-card"><el-form class="search-form" @submit.prevent="search"><el-input v-model="query.keyword" aria-label="面经搜索关键词" placeholder="公司、岗位、轮次，例如：字节 AI 应用开发 一面 面经" clearable :disabled="searching || collecting" /><el-select v-model="query.sort" aria-label="搜索排序" :disabled="searching || collecting"><el-option v-for="value in ['综合', '最新', '最多点赞', '最多收藏']" :key="value" :value="value" :label="value" /></el-select><el-select v-model="query.period" aria-label="发布时间" :disabled="searching || collecting"><el-option v-for="value in ['不限', '一天内', '一周内', '半年内']" :key="value" :value="value" :label="value === '不限' ? '不限时间' : value" /></el-select><el-button type="primary" icon="Search" native-type="submit" :loading="searching" :disabled="!query.keyword.trim() || collecting">搜索面经</el-button></el-form><p class="hint">搜索图文笔记，选中后采集正文与图片地址。图片识别和 AI 整理在本地资料中单独进行。</p></el-card>
      <div v-if="hasSearched" class="result-head"><span>本次返回 {{ hits.length }} 条笔记 <small>不代表全部搜索结果</small></span><el-button type="primary" plain :loading="collecting" :disabled="!selected.length || searching" @click="collect">{{ collecting ? `正在采集 ${collectIndex}/${selected.length}` : `采集已选 ${selected.length} 条` }}</el-button></div>
      <el-alert v-if="collectErrors.length" type="warning" :closable="true" :title="`${collectErrors.length} 条未采集成功，可重新勾选后重试；成功的资料已保存`" />
      <el-checkbox-group v-if="hits.length" v-model="selected" :max="5" class="results"><el-card v-for="hit in hits" :key="hit.id" shadow="never" class="result-card"><div class="cover"><img v-if="hit.cover" :src="hit.cover" alt="笔记封面" loading="lazy" referrerpolicy="no-referrer" /><div v-else class="no-cover"><el-icon><Document /></el-icon></div><el-tag v-if="hit.savedId" class="saved-badge" type="success">已采集</el-tag></div><div class="result-body"><el-checkbox v-if="!hit.savedId" :value="hit.id" :disabled="collecting"><span class="result-title">{{ hit.title }}</span></el-checkbox><strong v-else class="result-title">{{ hit.title }}</strong><div class="result-meta"><span>{{ hit.author || '作者未提供' }}</span><span v-if="hit.likes">{{ hit.likes }} 赞</span></div><el-button v-if="hit.savedId" link type="primary" @click="open(hit.savedId)">查看本地资料</el-button></div></el-card></el-checkbox-group>
      <el-empty v-else :description="hasSearched ? '没有返回相关笔记，试试更具体的公司、岗位或面经关键词' : '输入关键词搜索，或手动导入已有的面经正文'" :image-size="85" />
      <p v-if="hits.length" class="hint">每次最多勾选 5 条，逐条采集；相同笔记不会重复保存。搜索结果有效期约 30 分钟，过期后重新搜索。</p>
    </template>
    <template v-else>
      <div class="library-toolbar"><el-input v-model="filter" placeholder="搜索标题、公司、岗位" prefix-icon="Search" clearable aria-label="筛选本地面经" /><el-button icon="Refresh" @click="loadNotes">刷新资料</el-button></div>
      <div v-loading="notesLoading" class="library-list"><el-card v-for="note in filteredNotes" :key="note.id" shadow="never" class="library-card" @click="open(note.id)"><div class="library-heading"><h3>{{ note.title }}</h3><el-tag :type="note.workStatus === 'failed' ? 'warning' : note.questionCount ? 'success' : 'info'">{{ note.workStatus === 'pending' ? '正在处理' : note.workStatus === 'failed' ? '处理未完成' : note.questionCount ? `${note.questionCount} 道题` : '待整理' }}</el-tag></div><p>{{ [note.company, note.position, note.author].filter(Boolean).join(' · ') || (note.platform === 'manual' ? '手动导入' : '小红书面经') }}</p><div class="library-meta"><span>{{ note.imageCount }} 张图片 · {{ dayjs(note.updatedAt).format('MM-DD HH:mm') }}</span><el-button link type="primary">查看与整理 →</el-button></div></el-card><el-empty v-if="!filteredNotes.length" description="还没有面经资料，先搜索采集或手动导入" :image-size="85" /></div>
    </template>
    <CollectorConnection v-model="connectionOpen" @connected="connected = true" />
    <el-dialog v-model="manualOpen" title="手动导入面经" width="min(760px, calc(100vw - 32px))" :close-on-click-modal="false"><el-form label-position="top" @submit.prevent="saveManual"><el-form-item label="资料标题"><el-input v-model="manual.title" :maxlength="300" /></el-form-item><el-form-item label="来源链接（可选）"><el-input v-model="manual.sourceUrl" placeholder="保留来源，便于以后核对" /></el-form-item><el-form-item label="面经正文"><el-input v-model="manual.content" type="textarea" :rows="12" :maxlength="60000" show-word-limit placeholder="粘贴你已经获取的面经文字，保存后可用 AI 整理" /></el-form-item></el-form><template #footer><el-button @click="manualOpen = false">取消</el-button><el-button type="primary" :loading="importing" :disabled="!manual.title.trim() || !manual.content.trim()" @click="saveManual">保存资料</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import * as api from '../api'
import type { NoteSummary, SearchHit } from '../types'
import CollectorConnection from '../components/CollectorConnection.vue'
import ExperienceDetail from '../components/ExperienceDetail.vue'
const route = useRoute(), router = useRouter()
const noteId = computed(() => { const id = Number(route.query.note); return Number.isInteger(id) && id > 0 ? id : null })
const tab = computed({ get: () => route.query.tab === 'library' ? 'library' : 'search', set: value => { void router.replace({ path: '/experiences', query: value === 'library' ? { tab: value } : {} }) } })
const query = reactive({ keyword: '', sort: '综合', period: '不限' })
const searching = ref(false), collecting = ref(false), hasSearched = ref(false), importing = ref(false), notesLoading = ref(false)
const collectIndex = ref(0), hits = ref<SearchHit[]>([]), selected = ref<string[]>([]), collectErrors = ref<string[]>([])
const notes = ref<NoteSummary[]>([]), filter = ref(''), connectionOpen = ref(false), manualOpen = ref(false), connected = ref(false)
const manual = reactive({ title: '', sourceUrl: '', content: '' })
const filteredNotes = computed(() => { const keyword = filter.value.trim().toLowerCase(); return notes.value.filter(note => [note.title, note.company, note.position].join(' ').toLowerCase().includes(keyword)) })
async function loadNotes() { notesLoading.value = true; try { notes.value = await api.fetchNotes() } catch { /* 已有列表保留。 */ } finally { notesLoading.value = false } }
async function search() { searching.value = true; try { const result = await api.searchNotes(query); hits.value = result.items; selected.value = []; hasSearched.value = true; collectErrors.value = [] } catch { /* 保留上次结果。 */ } finally { searching.value = false } }
async function collect() { collecting.value = true; collectErrors.value = []; collectIndex.value = 0; const ids = [...selected.value]; for (const id of ids) { ++collectIndex.value; try { const note = await api.collectNote(id); const hit = hits.value.find(item => item.id === id); if (hit) hit.savedId = note.id } catch { collectErrors.value.push(id) } }; selected.value = [...collectErrors.value]; collecting.value = false; await loadNotes(); if (ids.length > collectErrors.value.length) ElMessage.success(`已保存 ${ids.length - collectErrors.value.length} 条，可到本地资料核对和整理`) }
async function open(id: number) { await router.push({ path: '/experiences', query: { note: id } }) }
async function back() { await router.push({ path: '/experiences', query: { tab: 'library' } }); await loadNotes() }
async function saveManual() { importing.value = true; try { const note = await api.importManual(manual); manualOpen.value = false; Object.assign(manual, { title: '', sourceUrl: '', content: '' }); await loadNotes(); await open(note.id); ElMessage.success(note.alreadySaved ? '相同正文已保存，已打开已有资料' : '面经资料已保存') } catch { /* 保留输入。 */ } finally { importing.value = false } }
onMounted(loadNotes)
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.page-head, .actions, .result-head, .library-toolbar, .library-heading, .library-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h1 { margin: 0; color: var(--ink); font-size: 21px; }
.sub { color: var(--ink-3); font-size: 13px; margin: 7px 0 0; }
.actions .el-button + .el-button { margin-left: 0; }
.hint { color: var(--ink-3); font-size: 12px; line-height: 1.8; margin: 10px 0 0; }
.search-card, .result-card, .library-card { border-radius: var(--radius-card); }
.search-form { display: grid; grid-template-columns: minmax(240px, 1fr) 125px 130px auto; gap: 12px; }
.result-head { font-size: 14px; color: var(--ink-2); }
.result-head small { color: var(--ink-3); margin-left: 10px; }
.results { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 18px; }
.result-card { overflow: hidden; }
.result-card :deep(.el-card__body) { padding: 0; }
.cover { position: relative; height: 240px; background: var(--surface-sunken); overflow: hidden; }
.cover img { width: 100%; height: 100%; object-fit: cover; }
.no-cover { display: grid; place-items: center; height: 100%; color: var(--el-color-primary-light-5); font-size: 38px; }
.saved-badge { position: absolute; top: 10px; left: 10px; }
.result-body { padding: 15px; }
.result-body :deep(.el-checkbox) { height: auto; align-items: flex-start; max-width: 100%; }
.result-body :deep(.el-checkbox__input) { margin-top: 3px; }
.result-body :deep(.el-checkbox__label) { min-width: 0; }
.result-title { white-space: normal; color: var(--ink); font-size: 14px; line-height: 1.7; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
.result-meta { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: var(--ink-3); margin: 13px 0 7px; }
.library-toolbar .el-input { max-width: 500px; }
.library-list { display: grid; gap: 14px; }
.library-card { cursor: pointer; }
.library-card:hover { border-color: var(--el-color-primary-light-5); }
.library-heading h3 { margin: 0; font-size: 15px; color: var(--ink); }
.library-card p, .library-meta { color: var(--ink-3); font-size: 12px; }
@media (max-width: 900px) { .search-form { grid-template-columns: 1fr 1fr; } .search-form > .el-input { grid-column: 1 / -1; } .page-head { align-items: flex-start; flex-direction: column; } }
@media (max-width: 520px) { .results { grid-template-columns: 1fr; } .result-head { flex-wrap: wrap; } .result-head small { display: block; margin: 5px 0; } .actions { flex-wrap: wrap; } .library-heading { align-items: flex-start; } }
</style>
