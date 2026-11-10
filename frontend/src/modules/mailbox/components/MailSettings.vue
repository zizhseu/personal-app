<template>
  <el-card v-loading="loading" shadow="never" class="mail-settings">
    <div class="heading">
      <div><h2>163 邮箱</h2><p>扫描新增招聘邮件，识别后同步到对应岗位流程。</p></div>
      <el-tag :type="saved?.account ? 'success' : 'info'">{{ saved?.account ? '已连接' : '待连接' }}</el-tag>
    </div>
    <el-alert v-if="loadFailed" title="邮箱设置读取失败" type="error" :closable="false">
      <template #default><el-button size="small" @click="load">重新读取</el-button></template>
    </el-alert>
    <el-form v-else label-position="top" :disabled="busy" class="settings-form" @submit.prevent>
      <div class="fields">
        <el-form-item label="163 邮箱地址">
          <el-input v-model="draft.address" placeholder="你的邮箱@163.com" aria-label="163 邮箱地址" autocomplete="off" />
        </el-form-item>
        <el-form-item label="客户端授权码">
          <el-input v-model="draft.authorizationCode" type="password" show-password autocomplete="new-password" aria-label="163 客户端授权码" :placeholder="saved?.authorizationConfigured && draft.address === saved.account?.address ? '已保存，留空保留' : '在 163 网页邮箱开启 IMAP 后获取'" />
        </el-form-item>
      </div>
      <p class="note">请在 163 网页邮箱的设置中开启 IMAP/SMTP 服务并获取客户端授权码。授权码保存在后端本机，Windows 下加密保存。</p>
      <el-form-item label="定时扫描">
        <el-switch v-model="draft.enabled" active-text="每小时扫描一次" aria-label="每小时扫描邮箱" />
      </el-form-item>
      <el-alert title="首次连接从当前时刻开始收取新邮件" type="info" :closable="false">
        <template #default>手动与定时扫描共用增量记录。已读邮件也会检查，正文用于分析，附件暂保留文件名供核对。</template>
      </el-alert>
      <div class="actions">
        <el-button type="primary" :loading="saving" :disabled="!draft.address || saved?.account?.scanning" @click="save">保存并连接</el-button>
        <el-button :loading="testing" :disabled="!draft.address" @click="test">测试连接</el-button>
        <RouterLink to="/aitools/mailbox">查看邮件处理记录</RouterLink>
      </div>
      <p v-if="saved?.account" class="note">已建立基线 {{ formatDateTime(saved.account.baselineAt) }} · 上次扫描 {{ formatDateTime(saved.account.lastScanAt) }}</p>
      <el-alert v-if="saved?.account?.lastError" :title="saved.account.lastError" type="warning" :closable="false" />
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { formatDateTime } from '@/shared/utils/format'
import * as api from '../api'
import type { MailDraft, MailSettings } from '../types'

const saved = ref<MailSettings | null>(null)
const draft = reactive<MailDraft>({ address: '', authorizationCode: '', enabled: true })
const loading = ref(false), saving = ref(false), testing = ref(false), loadFailed = ref(false)
const busy = computed(() => saving.value || testing.value)

async function load() {
  loading.value = true
  try {
    saved.value = await api.getMailSettings()
    draft.address = saved.value.account?.address ?? ''
    draft.enabled = saved.value.account?.enabled ?? true
    loadFailed.value = false
  } catch { loadFailed.value = true }
  finally { loading.value = false }
}
async function save() {
  saving.value = true
  try {
    saved.value = await api.saveMailSettings(draft)
    draft.address = saved.value.account!.address
    draft.authorizationCode = ''
    ElMessage.success('邮箱已连接，将按增量记录处理新邮件')
  } catch { /* 请求错误由统一入口显示。 */ }
  finally { saving.value = false }
}
async function test() {
  testing.value = true
  try { await api.testMailSettings(draft); ElMessage.success('163 邮箱连接成功') }
  catch { /* 请求错误由统一入口显示。 */ }
  finally { testing.value = false }
}
onMounted(load)
</script>

<style scoped>
.mail-settings { border-radius: var(--radius-card); }
.heading { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
h2 { margin: 0; font-size: 17px; color: var(--ink); }
p { margin: 6px 0 0; font-size: 13px; color: var(--ink-3); }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.note { margin: 0 0 18px; font-size: 12px; line-height: 1.7; }
.actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin: 18px 0; }
.actions a { font-size: 13px; color: var(--el-color-primary); }
@media (max-width: 700px) { .fields { grid-template-columns: 1fr; gap: 0; } }
</style>
