/** 笔试选择分类（用户可增删改的实体） */
export interface QuizCategory {
  id: number
  name: string
  createdAt: string
  updatedAt: string
}

/** 选择题类型 */
export type QuizType = 'single' | 'multi'

/** 笔试选择题 */
export interface QuizItem {
  id: number
  categoryId: number
  categoryName: string | null
  /** 题干 */
  question: string
  /** 选项文本数组（不含 A/B/C 前缀，前端按下标渲染字母） */
  options: string[]
  /** 正确选项下标数组（单选 1 个，多选多个） */
  answer: number[]
  qtype: QuizType
  /** 解析 */
  analysis: string | null
  createdAt: string
  updatedAt: string
}

/** 新增/编辑表单 */
export interface QuizPayload {
  categoryId: number
  question: string
  options: string[]
  answer: number[]
  qtype: QuizType
  analysis?: string | null
}

/** AI 解析出的候选题目（未入库） */
export interface ParsedQuiz {
  question: string
  options: string[]
  answer: number[]
  qtype: QuizType
  analysis: string
}

/** 答案/解析显示时机 */
export type QuizAnswerMode = 'instant' | 'afterAnswer' | 'manual'