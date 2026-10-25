export interface CodingCategory { id: number; name: string }
export type CodingStatus = 'todo' | 'practicing' | 'mastered'
export type CodingDifficulty = 'easy' | 'medium' | 'hard'
export interface CodingSummary {
  id: number; categoryId: number; title: string; sourceUrl: string; language: string
  difficulty: CodingDifficulty; status: CodingStatus; tags: string[]; createdAt: string; updatedAt: string
}
export interface CodingItem extends CodingSummary { description: string; code: string; approach: string; complexity: string }
export type CodingPayload = Omit<CodingItem, 'id' | 'createdAt' | 'updatedAt'>
export const statuses: Record<CodingStatus, string> = { todo: '待练习', practicing: '练习中', mastered: '已掌握' }
export const difficulties: Record<CodingDifficulty, string> = { easy: '简单', medium: '中等', hard: '困难' }
