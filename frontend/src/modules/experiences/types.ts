export interface SearchHit { id: string; sourceId: string; title: string; author: string; cover: string; likes: string; sourceUrl: string; savedId?: number | null }
export interface MaterialSource { id: string; label: string; text: string; originalText: string }
export interface NoteImage { id: string; url: string; status: 'pending' | 'done' | 'failed'; error: string | null; confidence?: number | null; stored?: boolean }
export interface ExtractedQuestion { question: string; sourceId: string; quote: string; topics: string[] }
export interface ExperienceReport { company: string | null; position: string | null; round: string | null; summary: string; questions: ExtractedQuestion[] }
export interface NoteSummary { id: number; platform: string; sourceId: string; sourceUrl: string; title: string; author: string; publishedAt: string | null; revision: number; imageCount: number; questionCount: number; company: string | null; position: string | null; workId: string | null; workKind: string | null; workStatus: 'idle' | 'pending' | 'succeeded' | 'failed'; error: string | null; updatedAt: string }
export interface ExperienceNote extends NoteSummary { rawBody: string; images: NoteImage[]; sources: MaterialSource[]; report: ExperienceReport | null; reportId: string | null; actions: { itemIndex: number; reportId: string; qaId: number | null }[]; alreadySaved?: boolean }
export interface CollectorConnection { url: string; tokenConfigured: boolean; ocrReady: boolean }
