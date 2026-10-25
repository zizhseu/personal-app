<template>
  <el-dialog v-model="visible" :title="`${platformLabel} · ${providerInfo?.label ?? '连接采集器'}`" width="min(560px, calc(100vw - 32px))" @closed="stopPolling">
    <p class="intro">{{ providerInfo?.description }} 使用你为此采集方式单独扫码登录的账号。</p>
    <div class="connection-actions"><el-button v-if="providerInfo?.capabilities.managedInstall" type="primary" :loading="starting" :disabled="busy" @click="start">{{ providerInfo?.capabilities.connectionSettings ? '安装并启动采集服务' : '安装采集组件' }}</el-button><el-button :loading="checking" :disabled="busy" @click="check()">检查登录</el-button></div>
    <p class="hint">首次启动会下载采集组件和浏览器，需要联网。已启动时直接检查登录即可。</p>
    <el-alert v-if="startMessage" :title="startMessage" type="info" :closable="false" />
    <el-alert v-if="errorText" :title="errorText" type="error" :closable="false" show-icon class="connection-error" />
    <el-alert v-if="loggedIn" :title="platformLabel + '已登录，可以搜索并采集'" type="success" :closable="false" show-icon />
    <div v-else-if="providerInfo?.capabilities.qrLogin" class="login-area"><el-button :loading="qrLoading" :disabled="busy" @click="getQr">获取登录二维码</el-button><p class="hint">使用 {{ platformLabel }} App 扫码并确认，应用不会接收账号密码。</p><template v-if="qrImage"><img :src="qrImage" :alt="platformLabel + '登录二维码'" class="qr" /><p class="hint">{{ qrExpired ? '二维码已过期，请重新获取。' : '扫码后等待登录状态更新，也可点击检查登录。' }}</p></template></div>
    <el-collapse v-if="providerInfo?.capabilities.connectionSettings" class="advanced"><el-collapse-item title="连接设置" name="connection"><el-form label-position="top" @submit.prevent="save"><el-form-item label="本机服务地址"><el-input v-model="url" aria-label="采集服务地址" placeholder="http://127.0.0.1:18060" /></el-form-item><el-form-item label="服务鉴权令牌（可选）"><el-input v-model="token" type="password" show-password autocomplete="new-password" :placeholder="tokenConfigured ? '已保存，留空保留' : '服务启用鉴权时填写'" /><el-checkbox v-if="tokenConfigured" v-model="clearToken">保存时清除令牌</el-checkbox></el-form-item><el-button :loading="saving" @click="save">保存连接</el-button></el-form></el-collapse-item></el-collapse>
    <p class="hint">登录记录只保存在本机，各采集方式互不共用。<a :href="providerInfo?.homepage" target="_blank" rel="noopener noreferrer">采集工具说明</a></p>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '../api'
import { useSourceStore } from '../sourceStore'
const props = withDefaults(defineProps<{ platform?: string; providerId?: string }>(), { platform: 'xiaohongshu', providerId: '' })
const sources = useSourceStore()
const context = ref({ platform: 'xiaohongshu', providerId: 'xhs-mcp' })
const platformInfo = computed(() => sources.platforms.find(item => item.id === context.value.platform))
const platformLabel = computed(() => platformInfo.value?.label ?? '来源')
const providerInfo = computed(() => platformInfo.value?.providers.find(item => item.id === context.value.providerId))
const visible = defineModel<boolean>({ default: false })
const emit = defineEmits<{ connected: [] }>()
const url = ref('http://127.0.0.1:18060'), token = ref(''), clearToken = ref(false), tokenConfigured = ref(false)
const loggedIn = ref(false), starting = ref(false), checking = ref(false), qrLoading = ref(false), saving = ref(false), preparing = ref(false)
const qrImage = ref(''), qrExpired = ref(false), startMessage = ref('')
const errorText = ref('')
const busy = computed(() => starting.value || checking.value || qrLoading.value || saving.value || preparing.value)
let timer: ReturnType<typeof setTimeout> | undefined
let expiresAt = 0
let generation = 0
function stopPolling() { clearTimeout(timer); ++generation; starting.value = false; checking.value = false; qrLoading.value = false; saving.value = false; preparing.value = false; token.value = ''; qrImage.value = '' }
watch([visible, () => props.platform, () => props.providerId], async ([value]) => {
  stopPolling(); loggedIn.value = false; errorText.value = ''; startMessage.value = ''
  if (!value) return
  const current = generation
  preparing.value = true
  await sources.load(true)
  if (!visible.value || current !== generation) return
  context.value = { platform: props.platform, providerId: props.providerId || sources.active(props.platform)?.id || 'xhs-mcp' }
  try { const data = await api.fetchConnection(context.value); if (visible.value && current === generation) { url.value = data.url; tokenConfigured.value = data.tokenConfigured } }
  catch { /* 可重新安装或保存连接。 */ }
  finally { if (current === generation) preparing.value = false }
  // 打开弹窗先复用并验证已有登录，不自动开始新的扫码流程。
  if (visible.value && current === generation) await check(true)
})
function showError(error: unknown, fallback: string) { const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; errorText.value = typeof detail === 'string' ? detail : fallback }
async function start() { stopPolling(); errorText.value = ''; starting.value = true; const current = generation; try { const result = await api.startCollector(context.value); if (!visible.value || generation !== current) return; startMessage.value = result.message; timer = setTimeout(() => pollStartup(current), 3000) } catch (error) { if (generation === current) { starting.value = false; showError(error, '采集组件未启动，请重试') } } }
async function pollStartup(current: number) { if (!visible.value || generation !== current) return; try { const result = await api.fetchStartupStatus(context.value); if (!visible.value || generation !== current) return; startMessage.value = result.message; if (result.status === 'starting' || result.status === 'idle') { timer = setTimeout(() => pollStartup(current), 3000); return }; starting.value = false; if (result.status === 'failed') errorText.value = result.message } catch (error) { if (generation === current) { starting.value = false; showError(error, '未能读取启动状态，可重新检查登录') } } }
async function save() { const current = generation; saving.value = true; try { const data = await api.saveConnection(context.value, { url: url.value, token: token.value || undefined, clearToken: clearToken.value }); if (generation !== current || !visible.value) return; tokenConfigured.value = data.tokenConfigured; token.value = ''; clearToken.value = false; loggedIn.value = false; stopPolling(); ElMessage.success('采集连接已保存') } catch { /* 保留表单。 */ } finally { if (generation === current) saving.value = false } }
async function check(quiet = false) { errorText.value = ''; const current = generation; checking.value = true; try { const result = await api.fetchLogin(context.value, quiet); if (!visible.value || generation !== current) return; loggedIn.value = result.loggedIn; if (loggedIn.value) { stopPolling(); emit('connected') } else if (!quiet) ElMessage.info('尚未登录，请获取二维码扫码登录') } catch (error) { if (generation === current) showError(error, '未能检查登录状态，请重试') } finally { if (generation === current) checking.value = false } }
async function getQr() { stopPolling(); errorText.value = ''; const current = generation; qrLoading.value = true; try { const result = await api.fetchQr(context.value); if (!visible.value || generation !== current) return; loggedIn.value = result.loggedIn; if (result.loggedIn) { emit('connected'); return }; if (!result.image) { errorText.value = '采集组件未返回二维码，请稍后重试'; return }; qrImage.value = result.image; qrExpired.value = false; const timeout = Number(result.timeout); expiresAt = Date.now() + (Number.isFinite(timeout) ? Math.min(600, Math.max(30, timeout)) : 300) * 1000; timer = setTimeout(() => poll(current), 5000) } catch (error) { if (generation === current) showError(error, '二维码获取未完成，请稍后重试') } finally { if (generation === current) qrLoading.value = false } }
async function poll(current: number) { if (!visible.value || generation !== current) return; if (Date.now() > expiresAt) { qrExpired.value = true; return }; try { const result = await api.fetchLogin(context.value); if (!visible.value || generation !== current) return; if (result.loggedIn) { loggedIn.value = true; stopPolling(); emit('connected'); return } } catch (error) { if (generation === current) showError(error, '登录状态检查中断，扫码后可手动点击检查登录'); return }; timer = setTimeout(() => poll(current), 5000) }
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.intro { margin-top: 0; color: var(--ink-2); line-height: 1.8; }
.connection-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.connection-actions .el-button { margin-left: 0; }
.hint { color: var(--ink-3); font-size: 12px; line-height: 1.8; }
.login-area { margin: 22px 0; text-align: center; }
.qr { display: block; width: 230px; height: 230px; object-fit: contain; margin: 14px auto; }
.advanced { margin-top: 20px; }
.connection-error { margin-top: 12px; }
a { color: var(--accent); }
</style>
