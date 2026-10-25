<template>
  <div class="coding-list" v-loading="store.loading">
    <div class="page-head">
      <div><h1>{{ category?.name ?? '代码手撕' }}</h1><p class="sub">记录题目、实现与复盘 · 共 {{ categoryItems.length }} 道，已掌握 {{ mastered }} 道</p></div>
      <div class="actions"><el-button @click="createCategory">新建分类</el-button><el-button type="primary" icon="Plus" :disabled="!store.categories.length || store.failed || invalidCategory" @click="createItem">新增手撕题</el-button></div>
    </div>
    <el-alert v-if="store.failed" title="题目列表读取失败，请重试" type="error" :closable="false"><el-button link @click="store.loadAll">重新加载</el-button></el-alert>
    <el-empty v-else-if="invalidCategory" description="分类不存在或已删除"><el-button @click="router.push('/coding')">查看全部题目</el-button></el-empty>
    <template v-else>
      <div class="toolbar">
        <el-input v-model="keyword" prefix-icon="Search" placeholder="搜索题目 / 标签 / 编程语言" clearable aria-label="搜索手撕题" />
        <el-select v-model="status" aria-label="筛选掌握状态"><el-option label="全部状态" value="all" /><el-option v-for="(label, value) in statuses" :key="value" :label="label" :value="value" /></el-select>
        <el-select v-model="difficulty" aria-label="筛选题目难度"><el-option label="全部难度" value="all" /><el-option v-for="(label, value) in difficulties" :key="value" :label="label" :value="value" /></el-select>
      </div>
      <el-card shadow="never" class="list-card">
        <el-table v-if="filtered.length" :data="paged" @row-click="openItem" class="problem-table">
          <el-table-column label="题目" min-width="250"><template #default="{ row }"><span class="problem-title">{{ row.title }}</span><div class="tags"><el-tag v-for="tag in row.tags.slice(0, 3)" :key="tag" size="small" type="info" effect="plain">{{ tag }}</el-tag></div></template></el-table-column>
          <el-table-column label="分类" min-width="120"><template #default="{ row }">{{ categoryName(row.categoryId) }}</template></el-table-column>
          <el-table-column prop="language" label="语言" width="110" />
          <el-table-column label="难度" width="90"><template #default="{ row }"><el-tag :type="row.difficulty === 'easy' ? 'success' : row.difficulty === 'hard' ? 'danger' : 'warning'" effect="plain">{{ difficulties[row.difficulty as CodingDifficulty] }}</el-tag></template></el-table-column>
          <el-table-column label="掌握状态" width="110"><template #default="{ row }"><el-tag :type="row.status === 'mastered' ? 'success' : row.status === 'practicing' ? 'warning' : 'info'">{{ statuses[row.status as CodingStatus] }}</el-tag></template></el-table-column>
          <el-table-column label="最近更新" width="140"><template #default="{ row }">{{ dayjs(row.updatedAt).format('MM-DD HH:mm') }}</template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="{ row }"><el-button link type="danger" @click.stop="removeItem(row)">删除</el-button></template></el-table-column>
        </el-table>
        <el-empty v-else :description="!store.categories.length ? '先创建分类，例如算法、JavaScript 或项目手撕' : categoryItems.length ? '没有符合筛选条件的题目' : '还没有手撕题，点击新增开始记录'" :image-size="90" />
      </el-card>
      <el-pagination v-if="filtered.length > 10" v-model:current-page="page" :page-size="10" :total="filtered.length" layout="total, prev, pager, next" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { useCodingStore } from '../store'
import { createCategory } from '../actions'
import { difficulties, statuses, type CodingDifficulty, type CodingStatus, type CodingSummary } from '../types'

const route = useRoute(), router = useRouter(), store = useCodingStore()
const categoryId = computed(() => Number(route.params.id) || null)
const category = computed(() => store.categories.find(row => row.id === categoryId.value))
const invalidCategory = computed(() => store.loaded && categoryId.value !== null && !category.value)
const categoryItems = computed(() => store.items.filter(row => categoryId.value === null || row.categoryId === categoryId.value))
const mastered = computed(() => categoryItems.value.filter(row => row.status === 'mastered').length)
const keyword = ref(''), status = ref('all'), difficulty = ref('all'), page = ref(1)
const filtered = computed(() => categoryItems.value.filter(row =>
  (status.value === 'all' || row.status === status.value) && (difficulty.value === 'all' || row.difficulty === difficulty.value)
  && [row.title, row.language, ...row.tags].join(' ').toLowerCase().includes(keyword.value.trim().toLowerCase()),
).sort((left, right) => right.updatedAt.localeCompare(left.updatedAt) || right.id - left.id))
const paged = computed(() => filtered.value.slice((page.value - 1) * 10, page.value * 10))
const categoryName = (id: number) => store.categories.find(row => row.id === id)?.name ?? ''
watch([keyword, status, difficulty, categoryId], () => { page.value = 1 })
watch(() => filtered.value.length, length => { page.value = Math.min(page.value, Math.max(1, Math.ceil(length / 10))) })
function openItem(row: CodingSummary) { void router.push(`/coding/cat/${row.categoryId}/${row.id}`) }
function createItem() { const id = categoryId.value ?? store.categories[0]?.id; if (id) void router.push(`/coding/cat/${id}/new`) }
async function removeItem(row: CodingSummary) {
  const confirmed = await ElMessageBox.confirm(`删除「${row.title}」及其代码和复盘记录？`, '删除手撕题', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }).then(() => true).catch(() => false)
  if (confirmed) try { await store.remove(row.id) } catch { /* 请求失败时保留列表。 */ }
}
onMounted(store.ensureLoaded)
</script>

<style scoped>
.coding-list { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px; }
.toolbar .el-input { flex: 1; min-width: 220px; }
.toolbar .el-select { width: 150px; }
.list-card { border-radius: var(--radius-card); min-width: 0; }
.problem-table :deep(.el-table__row) { cursor: pointer; }
.problem-title { color: var(--ink); font-weight: 600; line-height: 1.8; overflow-wrap: anywhere; }
.tags { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
.el-pagination { align-self: flex-end; }
@media (max-width: 600px) { .toolbar .el-input { flex-basis: 100%; } .toolbar .el-select { flex: 1; min-width: 0; } }
</style>
