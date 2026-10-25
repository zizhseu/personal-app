import type { QuizAnswerMode } from '@/modules/quiz/types'

/** 全局应用偏好（localStorage 持久化，不进后端） */
export interface AppSettings {
  /** 导入题目时把文件名（去扩展名）作为标签加到该批题目 */
  importFilenameAsTag: boolean
  /** 选择题答案/解析显示时机：instant=立即显示 / afterAnswer=作答后显示 / manual=手动查看 */
  quizAnswerMode: QuizAnswerMode
}

export type ModelAuthMode = 'api_key' | 'chatgpt'
export type ModelProvider = 'deepseek' | 'openai' | 'custom'
export type ApiStyle = 'chat_completions' | 'responses'

export interface ModelDraft {
  authMode: ModelAuthMode
  provider: ModelProvider
  baseUrl: string
  model: string
  apiStyle: ApiStyle
  apiKey?: string
  clearApiKey?: boolean
  requiresApiKey: boolean
  accountId?: string
}

export interface ChatGPTAccount {
  id: string
  label: string
  email: string
  connected: boolean
  planEnabled: boolean
  needsWelcome: boolean
}

export interface ChatGPTAccounts {
  activeAccountId: string | null
  accounts: ChatGPTAccount[]
}

export interface ModelSettings {
  authMode: ModelAuthMode
  model: string
  llmReady: boolean
  source: 'saved' | 'environment'
  api: Omit<ModelDraft, 'authMode' | 'apiKey' | 'clearApiKey'> & { apiKeyConfigured: boolean }
  chatgptModel: string
  chatgptAccountId: string | null
  chatgpt: ChatGPTAccounts
}
