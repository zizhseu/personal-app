<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑日程' : '新增日程'"
    width="520px"
    :close-on-click-modal="false"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="如：字节跳动 宣讲会" />
      </el-form-item>
      <el-form-item label="类型" prop="eventType">
        <el-select v-model="form.eventType" style="width: 100%">
          <el-option
            v-for="(label, key) in EVENT_TYPE_LABELS"
            :key="key"
            :label="label"
            :value="key"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="时间" prop="eventTime">
        <el-date-picker
          v-model="form.eventTime"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          format="YYYY-MM-DD HH:mm"
          placeholder="选择日期和时间（精确到分钟）"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="地点">
        <el-input v-model="form.location" placeholder="如：线上 / 腾讯会议 / 大学生活动中心" />
      </el-form-item>
      <el-form-item label="关联投递">
        <el-select
          v-model="form.applicationId"
          filterable
          clearable
          placeholder="选择关联的投递记录（可选）"
          style="width: 100%"
        >
          <el-option v-for="a in store.applications" :key="a.id" :label="appLabel(a)" :value="a.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.note" type="textarea" :rows="3" placeholder="需要携带的材料、会议链接等" />
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
import type { Application, EventPayload, ScheduleEvent } from '../types'
import { EVENT_TYPE_LABELS } from '../constants'
import { useJobsStore } from '../store'

const props = defineProps<{
  /** 编辑时传入已有日程数据 */
  event?: ScheduleEvent | null
}>()

const store = useJobsStore()

const visible = defineModel<boolean>({ default: false })
const formRef = ref<FormInstance>()
const saving = ref(false)

const isEdit = computed(() => !!props.event?.id)

const emptyForm = (): EventPayload => ({
  title: '',
  eventType: 'talk',
  eventTime: null,
  location: null,
  note: null,
  applicationId: null,
})

const form = reactive<EventPayload>(emptyForm())

watch(visible, (v) => {
  if (v) {
    // 只拷贝表单关心的字段，避免把 id/createdAt 等额外属性带进 payload
    const e = props.event
    Object.assign(form, emptyForm(), {
      title: e?.title ?? '',
      eventType: e?.eventType ?? 'talk',
      eventTime: e?.eventTime ?? null,
      location: e?.location ?? null,
      note: e?.note ?? null,
      applicationId: e?.applicationId ?? null,
    })
  }
})

const rules: FormRules = {
  title: [{ required: true, message: '请填写日程标题', trigger: 'blur' }],
  eventTime: [{ required: true, message: '请选择日程时间', trigger: 'change' }],
}

function appLabel(a: Application) {
  return a.position ? `${a.company} · ${a.position}` : a.company
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const payload: EventPayload = {
      ...form,
      title: form.title.trim(),
      location: form.location?.trim() || null,
      // 清除关联时 select 给 undefined，归一为 null 才能把关联置空
      applicationId: form.applicationId ?? null,
    }
    if (isEdit.value) {
      await store.updateEvent(props.event!.id, payload)
    } else {
      await store.addEvent(payload)
    }
    visible.value = false
  } finally {
    saving.value = false
  }
}
</script>