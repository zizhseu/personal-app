<template>
  <el-card shadow="never" class="source-settings" v-loading="loading">
    <h2>内容采集来源</h2>
    <p class="intro">选择各平台使用的采集方式。登录分别管理，切换后已有资料和整理结果仍会保留。</p>
    <el-alert v-if="store.failed" title="未能读取采集设置" type="error" :closable="false"><el-button link @click="reload">重新加载</el-button></el-alert>
    <div v-for="platform in store.platforms" :key="platform.id" class="source-row">
      <div class="source-info"><h3>{{ platform.label }}</h3><p>{{ store.active(platform.id)?.description }}</p><small>新搜索使用当前方式，已有搜索结果仍由原方式读取。</small></div>
      <div class="source-actions">
        <el-select :model-value="platform.activeProvider" :disabled="switching === platform.id" :aria-label="`${platform.label}采集方式`" @change="switchProvider(platform.id, $event)"><el-option v-for="provider in platform.providers" :key="provider.id" :value="provider.id" :label="provider.label" /></el-select>
        <el-button :disabled="switching === platform.id" @click="configure(platform.id, platform.activeProvider)">连接与登录</el-button>
      </div>
    </div>
    <CollectorConnection v-model="connectionOpen" :platform="context.platform" :provider-id="context.providerId" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useSourceStore } from '../sourceStore'
import CollectorConnection from './CollectorConnection.vue'
const store = useSourceStore(), loading = ref(false), switching = ref(''), connectionOpen = ref(false)
const context = ref({ platform: 'xiaohongshu', providerId: 'xhs-mcp' })
async function reload() { loading.value = true; try { await store.load(true) } finally { loading.value = false } }
async function switchProvider(platform: string, provider: string) {
  switching.value = platform
  try { await store.select(platform, provider); ElMessage.success('采集方式已切换，新搜索立即生效') }
  catch { /* 保留原来的已保存选择。 */ }
  finally { switching.value = '' }
}
function configure(platform: string, providerId: string) { context.value = { platform, providerId }; connectionOpen.value = true }
onMounted(reload)
</script>

<style scoped>
.source-settings { border-radius: var(--radius-card); }
h2 { margin: 0; font-size: 17px; color: var(--ink); }
.intro, .source-info p { font-size: 13px; line-height: 1.8; color: var(--ink-2); }
.source-row { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 18px 0 4px; }
.source-info { min-width: 0; }
h3 { margin: 0; font-size: 14px; }
.source-info p { margin: 6px 0; }
small { color: var(--ink-3); font-size: 12px; line-height: 1.8; }
.source-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.source-actions .el-select { width: 220px; }
@media (max-width: 850px) { .source-row { align-items: stretch; flex-direction: column; } .source-actions .el-select { flex: 1; min-width: 180px; } }
</style>
