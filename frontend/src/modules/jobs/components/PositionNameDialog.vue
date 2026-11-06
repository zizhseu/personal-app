<template>
  <el-dialog
    v-model="visible"
    :title="group.position ? '编辑岗位名称' : '补填岗位名称'"
    width="min(440px, calc(100vw - 32px))"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <p class="position-context">{{ application?.company }} · 岗位记录 {{ group.displayOrder }}</p>
    <el-form ref="formRef" :model="form" label-position="top" @submit.prevent="save">
      <el-form-item
        label="岗位名称"
        prop="name"
        :rules="[{ required: true, whitespace: true, message: '请填写岗位名称', trigger: 'blur' }]"
      >
        <el-input v-model="form.name" maxlength="100" placeholder="填写这个岗位的名称" aria-label="岗位名称" :disabled="saving" autofocus />
      </el-form-item>
      <p class="position-hint">保存后将同步更新本岗位所属的 {{ group.rounds.length }} 个轮次、{{ group.statusHistory.length }} 条状态变化及 {{ group.resultHistory.length }} 条结果记录的岗位名称。</p>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存名称</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import type { PositionHistoryGroup } from '../history'
import type { PositionDeletePayload } from '../types'
import { useJobsStore } from '../store'

const props = defineProps<{ applicationId: number; group: PositionHistoryGroup }>()
const visible = defineModel<boolean>({ default: false })
const store = useJobsStore()
const application = computed(() => store.applications.find(item => item.id === props.applicationId))
const formRef = ref<FormInstance>()
const form = reactive({ name: '' })
const saving = ref(false)
const target = ref<PositionDeletePayload | null>(null)

watch(visible, value => {
  if (!value || !application.value) return
  form.name = props.group.position ?? ''
  // 打开时固定成员范围，提交时由后端核对期间是否发生归属或范围变化。
  target.value = {
    position: props.group.position,
    positionVersion: props.group.positionVersion,
    expectedPositionVersion: application.value.positionVersion,
    expectedRoundIds: props.group.rounds.map(item => item.id),
    expectedStatusHistoryIds: props.group.statusHistory.map(item => item.id),
    expectedResultHistoryIds: props.group.resultHistory.map(item => item.id),
  }
  formRef.value?.clearValidate()
})

async function save() {
  if (saving.value || !target.value || !await formRef.value?.validate().catch(() => false)) return
  saving.value = true
  try {
    await store.renamePosition(props.applicationId, { ...target.value, newPosition: form.name.trim() })
    visible.value = false
  } catch { /* 请求层提示错误，保留输入供用户核对或重试。 */ }
  finally { saving.value = false }
}
</script>

<style scoped>
.position-context { margin-top: 0; color: var(--ink-2); line-height: 1.7; }
.position-hint { margin-bottom: 0; color: var(--ink-3); font-size: 12px; line-height: 1.8; }
</style>
