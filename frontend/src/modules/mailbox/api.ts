import request from '@/shared/api/request'
import type { MailCompanyTarget, MailDraft, MailMessage, MailSettings, MailTarget, MessageList } from './types'

export const getMailSettings = () => request.get('/mailbox/settings') as Promise<MailSettings>
export const saveMailSettings = (draft: MailDraft) => request.put('/mailbox/settings', draft, { timeout: 40_000 }) as Promise<MailSettings>
export const testMailSettings = (draft: MailDraft) => request.post('/mailbox/settings/test', draft, { timeout: 40_000 }) as Promise<{ ok: boolean }>
export const getMailStatus = (silentError = false) => request.get('/mailbox/status', { silentError }) as Promise<Pick<MailSettings, 'account' | 'intervalMinutes'>>
export const scanMailbox = () => request.post('/mailbox/scan') as Promise<{ accepted: boolean }>
export const getMessages = (status: string, page: number, silentError = false) => request.get('/mailbox/messages', { params: { status: status === 'all' ? undefined : status, page }, silentError }) as Promise<MessageList>
export const getMessage = (id: number) => request.get(`/mailbox/messages/${id}`) as Promise<MailMessage>
export const getTargets = () => request.get('/mailbox/targets') as Promise<MailTarget[]>
export const getCompanyTargets = () => request.get('/mailbox/company-targets') as Promise<MailCompanyTarget[]>
export const retryMessage = (id: number) => request.post(`/mailbox/messages/${id}/retry`) as Promise<{ accepted: boolean }>
export const ignoreMessage = (id: number) => request.post(`/mailbox/messages/${id}/ignore`) as Promise<MailMessage>
export const applyMessage = (id: number, target: MailTarget, roundId?: number) => request.post(`/mailbox/messages/${id}/apply`, {
  applicationId: target.applicationId, positionVersion: target.positionVersion,
  position: target.position, expectedUpdatedAt: target.expectedUpdatedAt, expectedSnapshot: target.expectedSnapshot, roundId,
}) as Promise<MailMessage>
export const applyNewPosition = (id: number, target: MailCompanyTarget, position: string) => request.post(`/mailbox/messages/${id}/apply`, {
  applicationId: target.applicationId, positionVersion: target.expectedPositionVersion, position: null,
  expectedUpdatedAt: target.expectedUpdatedAt, newPosition: position,
  expectedCompanySnapshot: target.expectedCompanySnapshot,
}) as Promise<MailMessage>
