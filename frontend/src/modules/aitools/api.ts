import request, { AI_REQUEST_TIMEOUT_MS } from '@/shared/api/request'
import type { InterviewSession, InterviewSummary, ResumeDocument, ResumeInput, ResumeSummary, ReviewAction, ReviewActionInput } from './types'

export const fetchResumes = () => request.get('/aitools/resumes') as Promise<ResumeSummary[]>
export const fetchResume = (id: number) => request.get(`/aitools/resumes/${id}`) as Promise<ResumeDocument>
export const createResume = (data: ResumeInput) => request.post('/aitools/resumes', data) as Promise<ResumeDocument>
export const updateResume = (id: number, data: ResumeInput) => request.put(`/aitools/resumes/${id}`, data) as Promise<ResumeDocument>
export const deleteResume = (id: number) => request.delete(`/aitools/resumes/${id}`)

export function extractResume(file: File): Promise<ResumeInput> {
  const body = new FormData()
  body.append('file', file)
  return request.post('/aitools/resumes/extract', body, { timeout: 30_000 }) as Promise<ResumeInput>
}

export const fetchInterviews = () => request.get('/aitools/interviews') as Promise<InterviewSummary[]>
export const fetchInterview = (id: number) => request.get(`/aitools/interviews/${id}`) as Promise<InterviewSession>
export const createInterview = (data: { resumeId: number; targetRole: string; focus: string }) => request.post('/aitools/interviews', data) as Promise<InterviewSession>
export const deleteInterview = (id: number) => request.delete(`/aitools/interviews/${id}`)

export function generateInterview(id: number, action: 'start' | 'messages' | 'review' | 'retry', requestId: string, content?: string): Promise<InterviewSession> {
  return request.post(`/aitools/interviews/${id}/${action}`, { requestId, ...(content === undefined ? {} : { content }) }, { timeout: AI_REQUEST_TIMEOUT_MS }) as Promise<InterviewSession>
}

export const exportReview = (id: number, data: ReviewActionInput) => request.post(`/aitools/interviews/${id}/actions`, data) as Promise<ReviewAction>

export async function ttsToBlob(text: string, signal?: AbortSignal): Promise<Blob> {
  const resp = await fetch('/api/aitools/tts', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }), signal,
  })
  if (!resp.ok) throw new Error('语音合成暂时不可用')
  return resp.blob()
}

export const fetchStatus = () => request.get('/aitools/status') as Promise<{ llmReady: boolean; demoMode?: boolean; authMode?: string; model?: string }>
