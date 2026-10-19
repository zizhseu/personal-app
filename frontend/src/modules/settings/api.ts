import request, { AI_REQUEST_TIMEOUT_MS } from '@/shared/api/request'
import type { ChatGPTAccounts, ModelDraft, ModelSettings } from './types'

export const fetchModelSettings = () => request.get('/settings/model') as Promise<ModelSettings>
export const saveModelSettings = (data: ModelDraft) => request.put('/settings/model', data) as Promise<ModelSettings>
export const testModel = (data: ModelDraft) => request.post('/settings/model/test', data, { timeout: AI_REQUEST_TIMEOUT_MS }) as Promise<{ ok: boolean; model: string; latencyMs: number }>
export const fetchModels = (data: ModelDraft) => request.post('/settings/model/models', data, { timeout: 40_000 }) as Promise<{ models: { id: string; name: string }[] }>
export const fetchChatGPTAccounts = () => request.get('/settings/chatgpt') as Promise<ChatGPTAccounts>
export const startChatGPTLogin = (accountId?: string) => request.post('/settings/chatgpt/login', { accountId }) as Promise<{ attemptId: string; authorizationUrl: string; expiresAt: number }>
export const fetchChatGPTLogin = (attemptId: string) => request.get(`/settings/chatgpt/login/${encodeURIComponent(attemptId)}`) as Promise<{ status: string; message: string }>
export const cancelChatGPTLogin = (attemptId: string) => request.delete(`/settings/chatgpt/login/${encodeURIComponent(attemptId)}`)
export const selectChatGPTAccount = (accountId: string) => request.put('/settings/chatgpt/active', { accountId }) as Promise<ChatGPTAccounts>
export const disconnectChatGPT = (accountId: string) => request.delete(`/settings/chatgpt/${encodeURIComponent(accountId)}`, { timeout: 35_000 }) as Promise<{ revocationConfirmed: boolean }>
export const acknowledgeChatGPTWelcome = (accountId: string) => request.post(`/settings/chatgpt/${encodeURIComponent(accountId)}/welcome`)
