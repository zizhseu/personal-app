<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑轮次' : '添加轮次'"
    width="520px"
    :close-on-click-modal="false"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="轮次类型" prop="roundType">
        <el-select v-model="form.roundType" style="width: 100%">
          <el-option v-for="t in allowedTypes" :key="t" :label="ROUND_TYPE_LABELS[t]" :value="t" />
        </el-select>
        <div class="type-hint">轮次需与当前状态匹配：测评/笔试/面试轮次要先把状态改到对应阶段</div>
      </el-form-item>
      <el-form-item label="开始时间" prop="startAt">
        <el-date-picker
          v-model="form.startAt"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          format="YYYY-MM-DD HH:mm"
          placeholder="选择开始时间"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="持续时间">
        <el-input-number
          v-model="durationHours"
          :min="0"
          :max="24 * 30"
          :step="1"
          controls-position="right"
          style="width: 140px"
        />
        <span class="unit">小时</span>
        <span class="tip">默认 72 小时，截止时间自动计算</span>
      </el-form-item>
      <el-form-item label="截止时间">
        <span v-if="deadlineText" class="deadline">{{ deadlineText }}</span>
        <span v-else class="deadline empty">—（未填开始时间）</span>
      </el-form-item>
      <el-form-item label="结果">
        <el-select v-model="form.result" style="width: 100%">
          <el-option
            v-for="(label, key) in RESULT_LABELS"
            :key="key"
            :label="label"
            :value="key"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="复盘笔记">
        <el-input
          v-model="form.reviewNote"
          type="textarea"
          :rows="4"
          placeholder="面试问题、表现如何、下次注意什么…"
        />
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
import dayjs from 'dayjs'
import type { InterviewRound, RoundPayload, RoundType } from '../types'
import { ROUND_TYPE_LABELS, RESULT_LABELS, ROUND_TYPE_STATUS } from '../constants'
import { useJobsStore } from '../store'

const props = defineProps<{
  applicationId: number
  /** 编辑时传入已有轮次数据 */
  round?: InterviewRound | null
}>()

const store = useJobsStore()

const visible = defineModel<boolean>({ default: false })
const formRef = ref<FormInstance>()
const saving = ref(false)

const isEdit = computed(() => !!props.round?.id)

const app = computed(() => store.applications.find((a) => a.id === props.applicationId))

/** 当前状态下允许的轮次类型（硬约束：轮次需与状态匹配；「其他」不限） */
const allowedTypes = computed<RoundType[]>(() => {
  const all = Object.keys(ROUND_TYPE_LABELS) as RoundType[]
  const allowed = all.filter((t) => {
    const required = ROUND_TYPE_STATUS[t]
    return required === null || required === app.value?.status
  })
  // 编辑时保留原类型可选（用户可能后来改过状态）
  const cur = props.round?.roundType
  if (cur && !allowed.includes(cur)) allowed.push(cur)
  return allowed
})

const nowStr = () => dayjs().format('YYYY-MM-DDTHH:mm:ss')
const DEFAULT_DURATION_MINUTES = 72 * 60 // 默认持续 72 小时

const emptyForm = (): RoundPayload => ({
  roundType: 'first',
  startAt: nowStr(), // 开始时间默认此刻
  durationMinutes: DEFAULT_DURATION_MINUTES,
  result: 'pending',
  reviewNote: null,
})

const form = reactive<RoundPayload>(emptyForm())

/** 持续时间以小时编辑、分钟存储 */
const durationHours = computed<number | undefined>({
  get: () => (form.durationMinutes == null ? undefined : form.durationMinutes / 60),
  set: (v) => {
    form.durationMinutes = v == null ? null : Math.round(v * 60)
  },
})

/** 截止时间 = 开始时间 + 持续时间（实时预览，提交后由后端计算） */
const deadlineText = computed(() => {
  if (!form.startAt) return ''
  return dayjs(form.startAt).add(form.durationMinutes ?? 0, 'minute').format('YYYY-MM-DD HH:mm')
})

watch(visible, (v) => {
  if (v) {
    // 只拷贝表单关心的字段，避免把 id/applicationId 等额外属性带进 payload
    const r = props.round
    Object.assign(form, emptyForm(), {
      roundType: r?.roundType ?? allowedTypes.value[0] ?? 'other',
      // 老数据只有「计划时间」：回填为开始时间
      startAt: r?.startAt ?? r?.scheduledAt ?? (r ? null : nowStr()),
      durationMinutes: r ? (r.durationMinutes ?? null) : DEFAULT_DURATION_MINUTES,
      result: r?.result ?? 'pending',
      reviewNote: r?.reviewNote ?? null,
    })
  }
})

const rules: FormRules = {
  roundType: [{ required: true, message: '请选择轮次类型', trigger: 'change' }],
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    if (isEdit.value) {
      await store.updateRound(props.round!.id, form)
    } else {
      await store.addRound(props.applicationId, form)
    }
    visible.value = false
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.type-hint {
  flex-basis: 100%;
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.5;
}

.unit {
  margin-left: 8px;
  color: #6b7280;
}

.tip {
  margin-left: 12px;
  color: #9ca3af;
  font-size: 12px;
}

.deadline {
  color: #374151;
  font-weight: 500;
}

.deadline.empty {
  color: #9ca3af;
  font-weight: 400;
}
</style>