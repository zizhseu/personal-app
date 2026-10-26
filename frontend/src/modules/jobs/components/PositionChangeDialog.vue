<template>
  <el-dialog v-model="visible" title="更换岗位" width="min(480px, calc(100vw - 32px))" :close-on-click-modal="false">
    <p class="position-context">{{ application.company }} · 当前岗位：{{ application.position || '未填写' }}</p>
    <el-form ref="formRef" :model="form" label-position="top" @submit.prevent="save">
      <el-form-item label="新岗位" prop="position" :rules="[{ required: true, whitespace: true, message: '请填写岗位名称', trigger: 'blur' }]">
        <el-input v-model="form.position" maxlength="100" placeholder="填写新的岗位名称" aria-label="新岗位名称" :disabled="saving" />
      </el-form-item>
      <el-checkbox v-model="form.restart" :disabled="saving">重新从初筛开始</el-checkbox>
      <p class="position-hint">{{ form.restart ? '保存后将为该岗位新增初筛轮次，之前的流程和结果会保留。' : '继续当前阶段，并为新岗位单独记录后续流程。' }}</p>
    </el-form>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">确认变更</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import type { Application } from '../types'
import { useJobsStore } from '../store'
const props = defineProps<{ application: Application }>()
const visible = defineModel<boolean>({ default: false })
const store = useJobsStore(), formRef = ref<FormInstance>(), saving = ref(false)
const form = reactive({ position: '', restart: true })
let expectedVersion = 1
watch(visible, value => {
  if (!value) return
  form.position = ''; form.restart = true
  expectedVersion = props.application.positionVersion
  formRef.value?.clearValidate()
})
async function save() {
  if (saving.value || !await formRef.value?.validate().catch(() => false)) return
  saving.value = true
  try {
    await store.update(props.application.id, { position: form.position.trim(), restartProcess: form.restart, expectedPositionVersion: expectedVersion })
    visible.value = false
  } catch { /* 请求失败时保留输入，便于核对后重试。 */ }
  finally { saving.value = false }
}
</script>

<style scoped>
.position-context { margin-top: 0; color: var(--ink-2); line-height: 1.7; }
.position-hint { color: var(--ink-3); font-size: 12px; line-height: 1.8; }
</style>
