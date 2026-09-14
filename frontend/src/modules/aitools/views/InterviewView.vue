<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>AI 面试</h1>
        <p class="sub">从面试八股选题，AI 面试官语音提问、逐题追问并点评</p>
      </div>
      <div class="actions" v-if="phase === 'running'">
        <el-button :icon="muted ? 'Mute' : 'Bell'" @click="muted = !muted">
          {{ muted ? '语音已关' : '语音已开' }}
        </el-button>
        <el-button type="warning" plain @click="endInterview">结束面试</el-button>
      </div>
    </div>

    <!-- 未配置 Key 的提示 -->
    <el-alert
      v-if="!llmReady"
      type="warning"
      :closable="false"
      title="尚未配置大模型 API Key"
      description="在 backend/.env 中设置 LLM_API_KEY（参考 backend/.env.example，支持 DeepSeek / 智谱等 OpenAI 兼容服务），保存后重启后端即可。"
      show-icon
    />

    <!-- 准备态 -->
    <el-card v-if="phase === 'setup'" shadow="never" class="setup-card">
      <div class="setup-form">
        <div class="form-row">
          <span class="form-label">题库分类</span>
          <el-select v-model="setupCategoryId" style="width: 240px">
            <el-option v-for="c in qaStore.categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </div>
        <div class="form-row">
          <span class="form-label">题目范围</span>
          <el-checkbox v-model="onlyLearning">只抽「待复习」的题</el-checkbox>
          <span class="form-hint">当前可选 {{ pool.length }} 条</span>
        </div>
        <div class="form-row">
          <span class="form-label">题量</span>
          <el-input-number v-model="questionCount" :min="1" :max="Math.max(1, pool.length)" />
        </div>
        <div class="setup-tip">
          <p>流程：AI 面试官逐题语音提问 → 你打字或点麦克风口头回答 → AI 点评并追问 → 结束后给出整体总结。</p>
          <p class="soft">语音说明：面试官声音由 edge-tts 合成（需联网）；你的语音输入使用浏览器识别（Chrome/Edge 支持，Firefox 下隐藏麦克风按钮）。</p>
        </div>
        <el-button
          type="primary"
          size="large"
          :disabled="pool.length === 0 || !llmReady"
          @click="startInterview"
        >
          开始面试
        </el-button>
      </div>
    </el-card>

    <!-- 对话态 -->
    <template v-else>
      <el-card shadow="never" class="chat-card">
        <div class="chat-scroll" ref="chatScrollEl">
          <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
            <div
              v-if="m.role === 'assistant'"
              class="bubble md-body"
              v-html="renderMarkdown(m.content)"
            ></div>
            <div v-else class="bubble user-bubble">{{ m.content }}</div>
          </div>
          <div v-if="thinking" class="msg assistant">
            <div class="bubble thinking">面试官正在思考…</div>
          </div>
        </div>
      </el-card>

      <div class="input-bar">
        <el-button
          v-if="hasSpeechRecognition"
          :type="listening ? 'danger' : 'default'"
          :icon="listening ? 'Loading' : 'Microphone'"
          :disabled="thinking"
          @click="toggleMic"
        >
          {{ listening ? '停止识别' : '语音输入' }}
        </el-button>
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          :placeholder="listening ? '请对着麦克风回答…' : '输入你的回答（Enter 发送）'"
          @keydown.enter.exact.prevent="sendInput"
        />
        <el-button
          type="primary"
          :loading="thinking"
          :disabled="!input.trim()"
          @click="sendInput"
        >
          发送
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchStatus, interviewChat, ttsToBlob } from '../api'
import { useQaStore } from '@/modules/qa/store'
import type { ChatMessage } from '../types'
import { renderMarkdown, markdownToText } from '@/shared/utils/markdown'

const qaStore = useQaStore()

// ---------- 配置状态 ----------
const llmReady = ref(true)

onMounted(async () => {
  await qaStore.ensureLoaded()
  setupCategoryId.value = qaStore.categories[0]?.id ?? null
  try {
    llmReady.value = (await fetchStatus()).llmReady
  } catch {
    llmReady.value = false
  }
})

// ---------- 准备态 ----------
const setupCategoryId = ref<number | null>(null)
const onlyLearning = ref(true)
const questionCount = ref(3)

const pool = computed(() => {
  const cid = setupCategoryId.value
  if (!cid) return []
  return qaStore.items.filter(
    (i: { categoryId: number; status: string }) =>
      i.categoryId === cid && (!onlyLearning.value || i.status === 'learning'),
  )
})

// ---------- 面试对话 ----------
const phase = ref<'setup' | 'running'>('setup')
const messages = ref<ChatMessage[]>([])
const selectedIds = ref<number[]>([])
const input = ref('')
const thinking = ref(false)
const muted = ref(false)
const chatScrollEl = ref<HTMLElement>()
let currentAudio: HTMLAudioElement | null = null
let lockedQuestionIds: number[] = []

function scrollToBottom() {
  nextTick(() => {
    const el = chatScrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function startInterview() {
  const ids = pool.value.slice(0, questionCount.value).map((i: QaItem) => i.id)
  if (!ids.length) return
  lockedQuestionIds = ids
  messages.value = []
  phase.value = 'running'
  await send('开始面试')
}

async function sendFlow(text: string) {
  const content = text.trim()
  if (!content || thinking.value) return
  messages.value.push({ role: 'user', content })
  input.value = ''
  thinking.value = true
  scrollToBottom()
  try {
    const resp = await interviewChat({
      questionIds: lockedQuestionIds,
      history: messages.value
        .slice(0, -1)
        .map((m) => ({ role: m.role, content: m.content })),
      message: content,
    })
    messages.value.push({ role: 'assistant', content: resp.reply })
    if (!muted.value) void speak(resp.reply)
  } catch {
    // 错误提示已由 axios 拦截器弹出；保留用户消息便于重发
  } finally {
    thinking.value = false
    scrollToBottom()
  }
}

function sendInput() {
  const text = input.value.trim()
  if (!text) return
  void sendFlow(text)
}

function endInterview() {
  void sendFlow('（候选人请求结束面试，请给出整体评价与改进建议，然后输出「面试结束」）')
}

// ---------- TTS（面试官语音，基础档：edge-tts） ----------
async function speak(text: string) {
  if (muted.value) return
  try {
    if (currentAudio) currentAudio.pause()
    const plain = markdownToText(text).slice(0, 300)
    if (!plain) return
    const blob = await ttsToBlob(plain)
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    currentAudio = audio
    audio.onended = () => URL.revokeObjectURL(url)
    await audio.play()
  } catch {
    // 语音合成失败静默降级为纯文字，不打断面试
  }
}

// ---------- 语音识别（Web Speech API，基础档） ----------
interface SpeechRecognitionLike {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: ((e: unknown) => void) | null
  start(): void
  stop(): void
}

const SRClass: (new () => SpeechRecognitionLike) | undefined =
  (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike })
    .SpeechRecognition ??
  (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionLike })
    .webkitSpeechRecognition

const hasSpeechRecognition = !!SRClass
const listening = ref(false)
let recognition: SpeechRecognitionLike | null = null
let voiceBase = ''
let liveTranscript = ''

function toggleMic() {
  if (!SRClass) return
  if (listening.value) {
    // 用户主动停止
    listening.value = false
    recognition?.stop()
    return
  }
  const rec = new SRClass()
  rec.lang = 'zh-CN'
  rec.continuous = true      // 持续监听：说完一句不断开
  rec.interimResults = true  // 实时转写：边识别边出字
  voiceBase = input.value
  liveTranscript = ''
  rec.onresult = (e) => {
    // results 是从识别开始的累计结果（含已确认与中间结果），全量重建实时显示
    let text = ''
    for (let i = 0; i < e.results.length; i++) {
      text += e.results[i][0].transcript
    }
    liveTranscript = text
    input.value = voiceBase ? `${voiceBase} ${liveTranscript}` : liveTranscript
  }
  rec.onerror = (e) => {
    const err = (e as { error?: string }).error
    listening.value = false
    if (err === 'network') {
      ElMessage.error('语音识别服务连接失败：请确认网络可访问并开启系统代理后重试')
    } else if (err === 'not-allowed' || err === 'service-not-allowed') {
      ElMessage.error('麦克风权限被拒绝：请允许浏览器使用麦克风后重试')
    } else if (err === 'audio-capture') {
      ElMessage.error('未检测到麦克风设备，请检查设备后重试')
    } else if (err !== 'no-speech' && err !== 'aborted') {
      ElMessage.warning('语音识别中断，打字输入不受影响')
    }
    // no-speech / aborted：静默（onend 后自动重启）
  }
  // 断开后自动重启（用户未主动停止时）：覆盖 Chrome 的静息超时
  rec.onend = () => {
    if (listening.value) {
      liveTranscript = ''
      // 重连前把本轮结果并入 voiceBase，避免下一轮覆盖
      voiceBase = input.value
      try {
        rec.start()
      } catch {
        listening.value = false
      }
    }
  }
  recognition = rec
  listening.value = true
  rec.start()
}

// 「结束面试」也走同一条对话通道
watch(
  () => phase.value,
  () => scrollToBottom(),
)

function send(text: string) {
  void sendFlow(text)
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 准备态 */
.setup-form {
  max-width: 520px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.form-label {
  width: 72px;
  font-size: 13.5px;
  color: var(--ink-2);
  flex-shrink: 0;
}

.form-hint {
  font-size: 12.5px;
  color: var(--ink-3);
}

.setup-tip {
  font-size: 13px;
  color: var(--ink-2);
  background: #fafafb;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  padding: 10px 14px;
  line-height: 1.7;
}

.setup-tip p {
  margin: 2px 0;
}

.setup-tip .warn {
  color: #b45309;
}

/* 对话态 */
.chat-card :deep(.el-card__body) {
  padding: 16px;
}

.chat-scroll {
  height: calc(100vh - 380px);
  min-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 6px;
}

.msg {
  display: flex;
}

.msg.assistant {
  justify-content: flex-start;
}

.msg.user {
  justify-content: flex-end;
}

.bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
}

.msg.assistant .bubble {
  background: #f6f7f8;
  border: 1px solid var(--line-soft);
  color: var(--ink);
}

.msg.user .bubble {
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--line);
  color: var(--ink);
  white-space: pre-wrap;
}

.bubble.thinking {
  color: var(--ink-3);
}

.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.input-bar .el-input {
  flex: 1;
}
</style>