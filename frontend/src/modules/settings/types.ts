import type { QuizAnswerMode } from '@/modules/quiz/types'

/** 全局应用偏好（localStorage 持久化，不进后端） */
export interface AppSettings {
  /** 导入题目时把文件名（去扩展名）作为标签加到该批题目 */
  importFilenameAsTag: boolean
  /** 选择题答案/解析显示时机：instant=立即显示 / afterAnswer=作答后显示 / manual=手动查看 */
  quizAnswerMode: QuizAnswerMode
}