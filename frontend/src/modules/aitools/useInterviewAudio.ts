import { onBeforeUnmount, ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { markdownToText } from '@/shared/utils/markdown'
import { ttsToBlob } from './api'

interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: ((event: { error?: string }) => void) | null
  start(): void
  stop(): void
}

export function useInterviewAudio(input: Ref<string>) {
  const muted = ref(true)
  const listening = ref(false)
  const browser = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition }
  const RecognitionClass = browser.SpeechRecognition ?? browser.webkitSpeechRecognition
  const hasSpeechRecognition = !!RecognitionClass
  let recognition: Recognition | null = null
  let audio: HTMLAudioElement | null = null
  let audioUrl: string | null = null
  let controller: AbortController | null = null

  function stopAudio() {
    controller?.abort()
    controller = null
    audio?.pause()
    audio = null
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    audioUrl = null
  }

  async function speak(text: string) {
    if (muted.value) return
    stopAudio()
    const current = new AbortController()
    controller = current
    try {
      const blob = await ttsToBlob(markdownToText(text).slice(0, 600), current.signal)
      if (muted.value || current.signal.aborted) return
      audioUrl = URL.createObjectURL(blob)
      audio = new Audio(audioUrl)
      audio.onended = () => stopAudio()
      await audio.play()
    } catch {
      if (current.signal.aborted) return
      muted.value = true
      stopAudio()
      ElMessage.warning('语音播放暂时不可用，可以继续文字面试')
    }
  }

  function stopRecognition() {
    listening.value = false
    if (recognition) {
      recognition.onend = recognition.onresult = recognition.onerror = null
      try { recognition.stop() } catch { /* 浏览器可能已经结束识别。 */ }
      recognition = null
    }
  }

  function toggleMic() {
    if (!RecognitionClass) return
    if (listening.value) return stopRecognition()
    const rec = new RecognitionClass()
    rec.lang = 'zh-CN'
    rec.continuous = true
    rec.interimResults = true
    let base = input.value
    rec.onresult = (event) => {
      let text = ''
      for (let i = 0; i < event.results.length; i++) text += event.results[i]?.[0]?.transcript ?? ''
      input.value = base ? `${base} ${text}` : text
    }
    rec.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return
      listening.value = false
      ElMessage.warning(event.error === 'not-allowed' ? '请允许浏览器使用麦克风，也可以直接输入回答' : '语音识别已中断，可以继续输入回答')
    }
    rec.onend = () => {
      if (!listening.value) return
      base = input.value
      try { rec.start() } catch { listening.value = false }
    }
    recognition = rec
    try { rec.start(); listening.value = true } catch { stopRecognition() }
  }

  function toggleVoice() {
    muted.value = !muted.value
    if (muted.value) stopAudio()
  }

  function stopAll() { stopRecognition(); stopAudio() }
  onBeforeUnmount(stopAll)
  return { muted, listening, hasSpeechRecognition, speak, stopAll, stopRecognition, toggleMic, toggleVoice }
}
