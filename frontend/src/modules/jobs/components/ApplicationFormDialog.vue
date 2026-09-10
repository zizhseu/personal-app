<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑投递' : '新增投递'"
    width="560px"
    :close-on-click-modal="false"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="公司" prop="company">
        <el-input v-model="form.company" placeholder="公司名称" />
      </el-form-item>
      <el-form-item label="岗位" prop="position">
        <el-input v-model="form.position" placeholder="岗位名称（选填）" />
      </el-form-item>
      <el-form-item label="招聘渠道">
        <el-select v-model="form.channel" placeholder="选择渠道" filterable clearable style="width: 100%">
          <el-option v-for="c in CHANNELS" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="投递链接">
        <el-input v-model="form.url" placeholder="招聘页面 / JD 链接（选填，如 https://...）">
          <template #append>
            <el-icon><Link /></el-icon>
          </template>
        </el-input>
      </el-form-item>
      <el-form-item label="投递日期">
        <el-date-picker
          v-model="form.applyDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="薪资范围">
        <el-input v-model="form.salary" placeholder="如 20k-30k·14薪" />
      </el-form-item>
      <el-form-item label="工作地点">
        <el-input v-model="form.location" placeholder="如 北京 / 上海" />
      </el-form-item>
      <el-form-item label="当前状态">
        <el-select v-model="form.status" style="width: 100%">
          <el-option
            v-for="s in STATUS_ORDER"
            :key="s"
            :label="STATUS_LABELS[s]"
            :value="s"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.note" type="textarea" :rows="3" placeholder="JD 链接、内推人等备注信息" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { Application, ApplicationPayload, ApplicationStatus } from '../types'
import { STATUS_LABELS, STATUS_ORDER, CHANNELS } from '../constants'
import { today } from '@/shared/utils/format'
import { useJobsStore } from '../store'

const props = defineProps<{ application?: Application | null }>()
const emit = defineEmits<{ saved: [] }>()

const store = useJobsStore()

const visible = defineModel<boolean>({ default: false })
const formRef = ref<FormInstance>()
const saving = ref(false)

const isEdit = computed(() => !!props.application?.id)

const emptyForm = (): ApplicationPayload => ({
  company: '',
  position: null,
  channel: null,
  url: null,
  applyDate: today(), // 投递日期默认当天
  salary: null,
  location: null,
  status: 'applied',
  note: null,
})

const form = reactive<ApplicationPayload>(emptyForm())

watch(visible, (v) => {
  if (v) {
    // 只拷贝表单关心的字段，避免把 id/rounds/createdAt 等额外属性带进 payload
    const a = props.application
    Object.assign(form, emptyForm(), {
      company: a?.company ?? '',
      position: a?.position ?? null,
      channel: a?.channel ?? null,
      url: a?.url ?? null,
      // 新增时默认当天；编辑时保留原值
      applyDate: a?.applyDate ?? (a ? null : today()),
      salary: a?.salary ?? null,
      location: a?.location ?? null,
      status: a?.status ?? 'applied',
      note: a?.note ?? null,
    })
  }
})

const rules: FormRules = {
  company: [{ required: true, message: '请填写公司名称', trigger: 'blur' }],
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    // 岗位空值归一为 null；链接去掉首尾空格
    const payload: ApplicationPayload = {
      ...form,
      position: form.position?.trim() || null,
      url: form.url?.trim() || null,
    }
    if (isEdit.value) {
      await store.update(props.application!.id, payload)
    } else {
      await store.create(payload)
    }
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>