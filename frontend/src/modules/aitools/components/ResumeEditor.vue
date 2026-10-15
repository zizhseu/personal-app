<template>
  <el-dialog v-model="visible" :title="resumeId ? '编辑简历' : '新增简历'" width="840px" :close-on-click-modal="false" :show-close="!saving && !importing" :close-on-press-escape="!saving && !importing">
    <div class="import-row">
      <input ref="fileInput" type="file" accept=".pdf,.docx,.txt,.md,.markdown" hidden @change="importFile" />
      <el-button icon="Upload" :loading="importing" :disabled="saving || loading" @click="fileInput?.click()">导入文件</el-button>
      <span>PDF、DOCX、TXT、Markdown · 最大 5 MB</span>
    </div>
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item label="简历名称">
        <el-input v-model="draft.name" maxlength="100" placeholder="例如：AI 应用开发 · 秋招版" :disabled="saving || loading" />
      </el-form-item>
      <el-form-item label="简历内容">
        <el-input v-model="draft.content" type="textarea" :rows="15" maxlength="30000" show-word-limit placeholder="粘贴简历，或导入文件后核对文字。保留项目背景、个人职责、技术实现与结果，方便面试深入追问。" :disabled="saving || importing || loading" />
      </el-form-item>
    </el-form>
    <p class="hint">导入后请核对文字顺序和内容。已经开始的面试保留当时的简历快照。</p>
    <template #footer>
      <el-button @click="visible = false" :disabled="saving">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading || importing || !draft.name.trim() || !draft.content.trim()" @click="save">保存简历</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '../api'
import type { ResumeDocument } from '../types'

const visible = defineModel<boolean>({ default: false })
const props = defineProps<{ resumeId: number | null }>()
const emit = defineEmits<{ saved: [resume: ResumeDocument] }>()
const draft = reactive({ name: '', content: '' })
const importing = ref(false)
const saving = ref(false)
const loading = ref(false)
const fileInput = ref<HTMLInputElement>()
let editorVersion = 0

watch(visible, async (open) => {
  const version = ++editorVersion
  loading.value = false
  if (!open) return
  draft.name = ''; draft.content = ''
  const id = props.resumeId
  if (id) {
    loading.value = true
    try {
      const resume = await api.fetchResume(id)
      if (visible.value && editorVersion === version) Object.assign(draft, resume)
    } catch { /* 请求拦截器已显示错误。 */ }
    finally { if (editorVersion === version) loading.value = false }
  }
})

async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 5 * 1024 * 1024) { ElMessage.warning('简历文件不能超过 5 MB'); return }
  importing.value = true
  const version = editorVersion
  try {
    const extracted = await api.extractResume(file)
    if (visible.value && version === editorVersion) { draft.content = extracted.content; if (!draft.name.trim()) draft.name = extracted.name }
  } catch { /* 保留已有文本，方便直接粘贴。 */ }
  finally { importing.value = false }
}

async function save() {
  if (saving.value || importing.value || loading.value) return
  saving.value = true
  try {
    const payload = { name: draft.name.trim(), content: draft.content.trim() }
    const saved = props.resumeId ? await api.updateResume(props.resumeId, payload) : await api.createResume(payload)
    emit('saved', saved)
    visible.value = false
    ElMessage.success('简历已保存')
  } catch { /* 保留输入以便重试。 */ }
  finally { saving.value = false }
}
</script>

<style scoped>
.import-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.import-row span, .hint { color: var(--ink-3); font-size: 12px; line-height: 1.7; }
.hint { margin-bottom: 0; }
</style>
