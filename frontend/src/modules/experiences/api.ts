import request, { AI_REQUEST_TIMEOUT_MS } from '@/shared/api/request'
import type { CollectorConnection, ExperienceNote, MaterialSource, NoteSummary, SearchHit } from './types'

const root = '/experiences'
export const fetchConnection = () => request.get(`${root}/connection`) as Promise<CollectorConnection>
export const saveConnection = (data: { url: string; token?: string; clearToken: boolean }) => request.put(`${root}/connection`, data) as Promise<CollectorConnection>
export const startCollector = () => request.post(`${root}/connection/start`) as Promise<{ started: boolean; message: string }>
export const fetchStartupStatus = () => request.get(`${root}/connection/start-status`) as Promise<{ status: string; message: string }>
export const fetchLogin = () => request.get(`${root}/login`, { timeout: 110_000 }) as Promise<{ loggedIn: boolean }>
export const fetchQr = () => request.post(`${root}/login/qrcode`, {}, { timeout: 110_000 }) as Promise<{ loggedIn: boolean; image: string; timeout: string }>
export const searchNotes = (data: { keyword: string; sort: string; period: string }) => request.post(`${root}/search`, data, { timeout: 110_000 }) as Promise<{ items: SearchHit[]; keyword: string; expiresIn: number }>
export const collectNote = (resultId: string) => request.post(`${root}/collect`, { resultId }, { timeout: 110_000 }) as Promise<ExperienceNote>
export const importManual = (data: { title: string; content: string; sourceUrl: string }) => request.post(`${root}/manual`, data) as Promise<ExperienceNote>
export const fetchNotes = () => request.get(`${root}/notes`) as Promise<NoteSummary[]>
export const fetchNote = (id: number) => request.get(`${root}/notes/${id}`) as Promise<ExperienceNote>
export const saveMaterial = (id: number, revision: number, sources: MaterialSource[]) => request.put(`${root}/notes/${id}/material`, { revision, sources: sources.map(({ id, text }) => ({ id, text })) }) as Promise<ExperienceNote>
export const recognizeImages = (id: number) => request.post(`${root}/notes/${id}/ocr`, { requestId: crypto.randomUUID() }, { timeout: 195_000 }) as Promise<ExperienceNote>
export const analyzeNote = (id: number) => request.post(`${root}/notes/${id}/analyze`, { requestId: crypto.randomUUID() }, { timeout: AI_REQUEST_TIMEOUT_MS }) as Promise<ExperienceNote>
export const exportQuestion = (id: number, data: { reportId: string; itemIndex: number; categoryId: number; title: string }) => request.post(`${root}/notes/${id}/export`, data) as Promise<{ itemIndex: number; reportId: string; qaId: number | null }>
export const deleteNote = (id: number) => request.delete(`${root}/notes/${id}`)
