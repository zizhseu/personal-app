<template>
  <el-card v-loading="loading" shadow="never" class="model-card">
    <div class="model-heading">
      <div><h2>大模型</h2><p>选择 AI 面试与题目解析使用的模型，保存后立即生效。</p></div>
      <el-tag v-if="saved" :type="saved.llmReady ? 'success' : 'info'" effect="light">{{ saved.llmReady ? '已配置' : '待配置' }}</el-tag>
    </div>
    <el-alert v-if="loadFailed" type="error" :closable="false" title="模型设置读取失败">
      <template #default><el-button size="small" @click="load">重新读取</el-button></template>
    </el-alert>
    <template v-else-if="saved">
      <div class="model-layout">
        <div class="model-main">
          <el-radio-group v-model="authMode" :disabled="busy || !!attemptId" class="auth-mode" aria-label="模型接入方式">
            <el-radio-button value="api_key">API Key</el-radio-button>
            <el-radio-button value="chatgpt">ChatGPT 账号</el-radio-button>
          </el-radio-group>
          <el-form label-position="top" :disabled="busy" class="model-form" @submit.prevent>
            <template v-if="authMode === 'api_key'">
              <div class="form-grid">
                <el-form-item label="模型服务" class="wide">
                  <el-select v-model="draft.provider" aria-label="模型服务" @change="changeProvider">
                    <el-option label="DeepSeek" value="deepseek" />
                    <el-option label="OpenAI API" value="openai" />
                    <el-option label="自定义 / 本地兼容服务" value="custom" />
                  </el-select>
                </el-form-item>
                <el-form-item label="服务地址（Base URL）" class="wide">
                  <el-input v-model="draft.baseUrl" placeholder="https://api.example.com/v1" autocomplete="off" aria-label="服务地址" />
                  <p class="field-note">填写服务商提供的基础地址，通常包含 /v1；也支持本机地址。</p>
                </el-form-item>
                <el-form-item label="API Key" class="wide">
                  <el-input v-model="apiKey" type="password" show-password autocomplete="new-password" :disabled="clearApiKey || !draft.requiresApiKey" :placeholder="savedKeyAvailable ? '已保存密钥，留空则保留；填写新值可替换' : '填写此服务的 API Key'" aria-label="API Key" />
                  <div class="key-options">
                    <span class="field-note">{{ savedKeyAvailable ? '此地址已有密钥。' : '此地址尚未保存密钥。' }}密钥只保存在后端本机。</span>
                    <el-checkbox v-if="savedKeyAvailable" v-model="clearApiKey">保存时清除密钥</el-checkbox>
                  </div>
                </el-form-item>
                <el-form-item label="接口格式">
                  <el-select v-model="draft.apiStyle" aria-label="接口格式">
                    <el-option label="Chat Completions（常见兼容接口）" value="chat_completions" />
                    <el-option label="Responses（OpenAI 等）" value="responses" />
                  </el-select>
                </el-form-item>
                <el-form-item label="连接认证">
                  <el-switch v-model="draft.requiresApiKey" active-text="使用 API Key" inactive-text="无需密钥" aria-label="使用 API Key" />
                </el-form-item>
              </div>
            </template>
            <template v-else>
              <div class="account-panel">
                <p class="account-intro">使用 ChatGPT 账号授权，符合条件的请求使用你的套餐或可用额度。</p>
                <el-form-item v-if="accounts.accounts.length" label="ChatGPT 连接">
                  <el-select :model-value="accounts.activeAccountId" :disabled="!!attemptId" aria-label="ChatGPT 连接" @change="chooseAccount">
                    <el-option v-for="account in accounts.accounts" :key="account.id" :value="account.id" :label="`${account.label} · ${account.email || 'ChatGPT 账号'}${account.connected ? '' : '（需登录）'}`" />
                  </el-select>
                </el-form-item>
                <div v-if="activeAccount" class="account-status">
                  <el-tag :type="activeAccount.connected && activeAccount.planEnabled ? 'success' : 'warning'">{{ activeAccount.connected ? (activeAccount.planEnabled ? '已授权套餐使用' : '尚未授权套餐使用') : '需要重新登录' }}</el-tag>
                  <a :href="usageUrl" target="_blank" rel="noopener noreferrer">管理 ChatGPT 用量</a>
                </div>
                <div class="account-actions">
                  <el-button class="chatgpt-login" :disabled="!!attemptId" @click="connect(activeAccount?.id)">Continue with ChatGPT</el-button>
                  <el-button v-if="activeAccount" text :disabled="!!attemptId" @click="connect()">连接另一个账号</el-button>
                  <el-button v-if="activeAccount?.connected" text type="danger" :disabled="!!attemptId" @click="disconnect">退出此连接</el-button>
                </div>
                <div v-if="attemptId" class="login-pending" role="status">
                  <span>{{ loginMessage }}</span>
                  <a v-if="authorizationUrl" :href="authorizationUrl" target="_blank" rel="noopener noreferrer">打开授权页面</a>
                  <el-button text size="small" @click="cancelLogin">取消登录</el-button>
                </div>
                <p class="field-note">官方账号接入仍有开放范围和套餐限制。请在 OpenAI 授权页面登录；应用不会接收你的账号密码。</p>
              </div>
            </template>
            <el-form-item label="模型名称" class="model-picker">
              <div class="model-picker-row">
                <el-select v-model="selectedModel" filterable allow-create :reserve-keyword="false" placeholder="获取列表后选择，或输入准确的模型名称" aria-label="模型名称">
                  <el-option v-for="model in modelOptions" :key="model.id" :label="model.name" :value="model.id" />
                </el-select>
                <el-button :loading="listing" :disabled="!canConnect || !!attemptId" @click="loadModels">获取模型列表</el-button>
              </div>
              <p class="field-note">模型列表仅供选择，是否可用请以连接测试为准。</p>
            </el-form-item>
            <div class="model-actions">
              <el-button type="primary" :loading="saving" :disabled="!canSave || !!attemptId" @click="save">保存配置</el-button>
              <el-button :loading="testing" :disabled="!canSave || !canConnect || !!attemptId" @click="test">测试连接</el-button>
              <span v-if="testResult" class="test-result" role="status"><el-icon><CircleCheck /></el-icon>{{ testResult }}</span>
            </div>
            <p class="field-note test-note">测试会发送一句固定文字，可能产生少量费用或套餐用量，不发送简历。测试不会保存配置。</p>
          </el-form>
        </div>
        <aside class="model-aside">
          <div class="aside-icon"><el-icon><Connection /></el-icon></div>
          <h3>一处配置，统一使用</h3>
          <p>AI 面试、回答追问、复盘和选择题解析使用这里保存的连接。</p>
          <div class="current-model"><span>当前已保存</span><strong>{{ saved.authMode === 'chatgpt' ? 'ChatGPT 账号' : providerName(saved.api.provider) }}</strong><code>{{ saved.model || '尚未选择模型' }}</code></div>
          <template v-if="authMode === 'chatgpt'"><h4>账号与 API Key 是两种接入</h4><p>ChatGPT 账号需要单独登录授权。OpenAI API 则填写平台生成的 API Key，按 API 的计费与权限调用。</p><a href="https://developers.openai.com/siwc/token-sharing-open-source" target="_blank" rel="noopener noreferrer">查看官方账号接入说明 ↗</a></template>
          <template v-else><h4>支持已有兼容服务</h4><p>可以填写云端服务地址，也可以连接你自己运行的本地服务。更换地址时请重新填写对应的密钥。</p></template>
          <p class="privacy-note"><el-icon><Lock /></el-icon>密钥与登录令牌不会写入浏览器缓存，也不会随代码上传。</p>
        </aside>
      </div>
    </template>
    <el-dialog v-model="welcomeOpen" title="已授权使用 ChatGPT 套餐" width="min(480px, calc(100vw - 32px))" :close-on-click-modal="false" :show-close="false">
      <p>选择并保存 ChatGPT 连接后，符合条件的 AI 请求会使用你的 ChatGPT 套餐或可用额度。你可以随时在 ChatGPT 设置中管理应用用量和访问权限。</p>
      <template #footer><a :href="usageUrl" target="_blank" rel="noopener noreferrer">管理用量</a><el-button type="primary" @click="acknowledgeWelcome">知道了</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { CircleCheck, Connection, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as api from '../api'
import type { ChatGPTAccounts, ModelAuthMode, ModelDraft, ModelProvider, ModelSettings } from '../types'

const usageUrl = 'https://chatgpt.com/settings/usage'
const loading = ref(true)
const loadFailed = ref(false)
const saved = ref<ModelSettings | null>(null)
const authMode = ref<ModelAuthMode>('api_key')
const draft = reactive<ModelDraft>({ authMode: 'api_key', provider: 'deepseek', baseUrl: '', model: '', apiStyle: 'chat_completions', requiresApiKey: true })
const apiKey = ref('')
const clearApiKey = ref(false)
const chatgptModel = ref('')
const accounts = ref<ChatGPTAccounts>({ activeAccountId: null, accounts: [] })
const modelOptions = ref<{ id: string; name: string }[]>([])
const saving = ref(false)
const testing = ref(false)
const listing = ref(false)
const accountBusy = ref(false)
const busy = computed(() => saving.value || testing.value || listing.value || accountBusy.value)
const attemptId = ref('')
const authorizationUrl = ref('')
const loginMessage = ref('')
const testResult = ref('')
const welcomeOpen = ref(false)
const welcomeAccountId = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false
const activeAccount = computed(() => accounts.value.accounts.find(account => account.id === accounts.value.activeAccountId))
const selectedModel = computed({ get: () => authMode.value === 'chatgpt' ? chatgptModel.value : draft.model, set: value => { if (authMode.value === 'chatgpt') chatgptModel.value = value; else draft.model = value } })
const providerName = (value: ModelProvider) => ({ deepseek: 'DeepSeek', openai: 'OpenAI API', custom: '自定义兼容服务' })[value]
function canonicalUrl(value: string) { try { const url = new URL(value.trim()); return `${url.origin}${url.pathname.replace(/\/+$/, '').replace(/\/(chat\/completions|responses|models)$/, '')}` } catch { return value.trim() } }
const savedKeyAvailable = computed(() => !!saved.value?.api.apiKeyConfigured && saved.value.api.provider === draft.provider && canonicalUrl(saved.value.api.baseUrl) === canonicalUrl(draft.baseUrl))
const canConnect = computed(() => authMode.value === 'chatgpt' ? !!activeAccount.value?.connected && !!activeAccount.value.planEnabled : !!draft.baseUrl.trim() && (!draft.requiresApiKey || (!clearApiKey.value && (!!apiKey.value.trim() || savedKeyAvailable.value))))
const canSave = computed(() => !!selectedModel.value.trim() && (authMode.value === 'chatgpt' ? canConnect.value : !!draft.baseUrl.trim()))
const payload = (): ModelDraft => ({ ...draft, authMode: authMode.value, model: selectedModel.value.trim(), ...(authMode.value === 'api_key' ? { apiKey: apiKey.value.trim() || undefined, clearApiKey: clearApiKey.value } : { accountId: accounts.value.activeAccountId ?? undefined }) })

function apply(value: ModelSettings) {
  saved.value = value
  authMode.value = value.authMode
  const { provider, baseUrl, model, apiStyle, requiresApiKey } = value.api
  Object.assign(draft, { provider, baseUrl, model, apiStyle, requiresApiKey })
  chatgptModel.value = value.chatgptModel
  accounts.value = value.chatgpt
  if (value.authMode === 'chatgpt' && value.chatgptAccountId) accounts.value.activeAccountId = value.chatgptAccountId
  apiKey.value = ''
  clearApiKey.value = false
}
async function load() {
  loading.value = true; loadFailed.value = false
  try { apply(await api.fetchModelSettings()); showWelcome() }
  catch { loadFailed.value = true }
  finally { loading.value = false }
}
function changeProvider(value: ModelProvider) {
  apiKey.value = ''; clearApiKey.value = false; modelOptions.value = []
  if (value === 'deepseek') { draft.baseUrl = 'https://api.deepseek.com'; draft.model = 'deepseek-chat'; draft.apiStyle = 'chat_completions'; draft.requiresApiKey = true }
  else if (value === 'openai') { draft.baseUrl = 'https://api.openai.com/v1'; draft.model = ''; draft.apiStyle = 'responses'; draft.requiresApiKey = true }
}
async function save() {
  saving.value = true
  try { const result = await api.saveModelSettings(payload()); apply(result); ElMessage.success('模型配置已保存，立即生效') }
  catch { /* 请求层已展示错误，保留表单以便修改。 */ }
  finally { saving.value = false }
}
async function test() {
  testing.value = true; testResult.value = ''
  try { const result = await api.testModel(payload()); testResult.value = `连接成功 · ${(result.latencyMs / 1000).toFixed(2)} 秒`; ElMessage.success('测试成功，需要保存后才会用于 AI 功能') }
  catch { /* 请求层已展示安全的连接错误。 */ }
  finally { testing.value = false }
}
async function loadModels() {
  listing.value = true
  try { modelOptions.value = (await api.fetchModels(payload())).models; if (!modelOptions.value.length) ElMessage.info('服务未返回可选模型，请手动填写模型名称') }
  catch { /* 允许手动填写，不影响保存。 */ }
  finally { listing.value = false }
}
function showWelcome() {
  const account = activeAccount.value
  if (account?.needsWelcome) { welcomeAccountId.value = account.id; welcomeOpen.value = true }
}
async function acknowledgeWelcome() {
  try { await api.acknowledgeChatGPTWelcome(welcomeAccountId.value); welcomeOpen.value = false; accounts.value = await api.fetchChatGPTAccounts() }
  catch { /* 保留确认入口供重试。 */ }
}
async function connect(accountId?: string) {
  const popup = window.open('about:blank', '_blank')
  if (popup) popup.opener = null
  accountBusy.value = true
  try {
    const result = await api.startChatGPTLogin(accountId)
    if (disposed) { popup?.close(); await api.cancelChatGPTLogin(result.attemptId); return }
    attemptId.value = result.attemptId; authorizationUrl.value = result.authorizationUrl
    loginMessage.value = '等待在授权页面完成登录…'
    if (popup) popup.location.replace(result.authorizationUrl)
    else ElMessage.info('请点击“打开授权页面”完成登录')
    timer = setTimeout(pollLogin, 2000)
  } catch { popup?.close() }
  finally { accountBusy.value = false }
}
async function pollLogin() {
  if (disposed || !attemptId.value) return
  const currentAttempt = attemptId.value
  try {
    const result = await api.fetchChatGPTLogin(currentAttempt)
    if (disposed || attemptId.value !== currentAttempt) return
    loginMessage.value = result.message
    if (result.status === 'pending' || result.status === 'processing') { timer = setTimeout(pollLogin, 2000); return }
    attemptId.value = ''; authorizationUrl.value = ''
    if (result.status === 'completed') { accounts.value = await api.fetchChatGPTAccounts(); modelOptions.value = []; chatgptModel.value = ''; showWelcome(); ElMessage.success(result.message) }
    else ElMessage.warning(result.message)
  } catch { if (!disposed && attemptId.value === currentAttempt) timer = setTimeout(pollLogin, 5000) }
}
async function cancelLogin() {
  clearTimeout(timer)
  try { await api.cancelChatGPTLogin(attemptId.value); attemptId.value = ''; authorizationUrl.value = '' }
  catch { /* 失败时保留取消入口。 */ }
}
async function chooseAccount(id: string) {
  accountBusy.value = true
  try { accounts.value = await api.selectChatGPTAccount(id); modelOptions.value = []; chatgptModel.value = ''; showWelcome(); if (saved.value) saved.value = await api.fetchModelSettings() }
  catch { /* 保留原选择。 */ }
  finally { accountBusy.value = false }
}
async function disconnect() {
  if (!activeAccount.value) return
  accountBusy.value = true
  try {
    const result = await api.disconnectChatGPT(activeAccount.value.id)
    accounts.value = await api.fetchChatGPTAccounts(); modelOptions.value = []; testResult.value = ''
    if (saved.value) saved.value = await api.fetchModelSettings()
    if (result.revocationConfirmed) ElMessage.success('已退出此 ChatGPT 连接')
    else ElMessage.warning('已在本机退出，未能确认远端撤销；可到 ChatGPT 设置中断开此应用')
  } catch { /* 请求层已展示错误。 */ }
  finally { accountBusy.value = false }
}
watch([authMode, () => draft.baseUrl, () => draft.provider, () => draft.apiStyle, () => draft.requiresApiKey, selectedModel, apiKey, clearApiKey, () => accounts.value.activeAccountId], () => { testResult.value = '' })
watch([authMode, () => draft.baseUrl, () => draft.provider], () => { modelOptions.value = [] })
onMounted(load)
onBeforeUnmount(() => { disposed = true; clearTimeout(timer); apiKey.value = ''; authorizationUrl.value = '' })
</script>

<style scoped>
.model-card { border-radius: var(--radius-card); }
.model-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 24px; }
h2 { margin: 0; font-size: 17px; color: var(--ink); }
.model-heading p { margin: 7px 0 0; color: var(--ink-3); font-size: 13px; }
.model-layout { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(260px, 1fr); gap: 32px; }
.model-main { min-width: 0; }
.auth-mode { margin-bottom: 24px; }
.model-form :deep(.el-select) { width: 100%; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 20px; }
.form-grid > * { min-width: 0; }
.wide { grid-column: 1 / -1; }
.field-note { margin: 6px 0 0; color: var(--ink-3); font-size: 12px; line-height: 1.65; font-weight: 400; }
.key-options { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 5px 16px; width: 100%; }
.model-picker-row { display: flex; gap: 10px; width: 100%; }
.model-picker-row .el-select { min-width: 0; flex: 1; }
.model-actions, .account-actions, .account-status { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.model-actions .el-button + .el-button, .account-actions .el-button + .el-button { margin-left: 0; }
.test-result { display: inline-flex; align-items: center; gap: 5px; color: var(--el-color-success); font-size: 13px; }
.test-note { margin-top: 12px; }
.model-aside { padding: 25px; background: var(--el-color-primary-light-9); border: 1px solid var(--el-color-primary-light-8); border-radius: 16px; align-self: stretch; min-width: 0; }
.aside-icon { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 12px; background: var(--el-color-primary-light-8); color: var(--el-color-primary); font-size: 20px; }
.model-aside h3 { margin: 16px 0 10px; font-size: 16px; color: var(--ink); }
.model-aside h4 { font-size: 13px; margin: 24px 0 8px; color: var(--ink); }
.model-aside p { color: var(--ink-3); font-size: 13px; line-height: 1.8; }
.current-model { display: flex; flex-direction: column; gap: 8px; padding: 18px 0; margin-top: 18px; border-top: 1px solid var(--el-color-primary-light-8); border-bottom: 1px solid var(--el-color-primary-light-8); }
.current-model span { font-size: 12px; color: var(--ink-3); }
.current-model strong { font-size: 14px; color: var(--ink); }
.current-model code { font-size: 13px; overflow-wrap: anywhere; color: var(--el-color-primary); }
a { color: var(--el-color-primary); font-size: 13px; text-decoration: none; }
a:hover { text-decoration: underline; }
.model-aside .privacy-note { margin-top: 28px; font-size: 12px; }
.privacy-note .el-icon { vertical-align: -2px; margin-right: 4px; }
.account-panel { margin-bottom: 24px; padding: 20px; border: 1px solid var(--line); border-radius: 12px; background: var(--el-fill-color-lighter); }
.account-intro { color: var(--ink-2); font-size: 13px; line-height: 1.7; margin: 0 0 18px; }
.account-actions { margin: 16px 0 12px; }
.chatgpt-login { color: #fff; background: #171717; border-color: #171717; }
.chatgpt-login:hover { color: #fff; background: #333; border-color: #333; }
.login-pending { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 10px 0; color: var(--ink-2); font-size: 13px; }
:deep(.el-dialog__footer) { display: flex; align-items: center; justify-content: flex-end; gap: 20px; }
@media (max-width: 1000px) { .model-layout { grid-template-columns: 1fr; gap: 24px; } }
@media (max-width: 600px) { .form-grid { grid-template-columns: 1fr; } .model-picker-row { flex-direction: column; } .model-picker-row .el-button { align-self: flex-start; } .model-aside { padding: 18px; } .account-panel { padding: 14px; } }
</style>
