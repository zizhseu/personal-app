import request from '@/shared/api/request'
import type { ChatMessage } from './types'

/** aitools 模块接口调用 */

/** AI 面试官对话 */
export function interviewChat(payload: {
  questionIds: number[]
  history: ChatMessage[]
  message: string
}): Promise<{ reply: string }> {
  return request.post('/aitools/interview/chat', payload) as Promise<{ reply: string }>
}

/** TTS：文本 → mp3 音频 Blob（用独立 fetch 以接收二进制） */
export async function ttsToBlob(text: string): Promise<Blob> {
  const resp = await fetch('/api/aitools/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!resp.ok) throw new Error('TTS 请求失败')
  return resp.blob()
}

/** LLM 是否已配置 Key */
export function fetchStatus(): Promise<{ llmReady: boolean }> {
  return request.get('/aitools/status') as Promise<{ llmReady: boolean }>
}