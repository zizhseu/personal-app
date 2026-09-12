import type { QaStatus } from './types'

/** 掌握状态 → 中文标签 */
export const QA_STATUS_LABELS: Record<QaStatus, string> = {
  learning: '待复习',
  mastered: '已掌握',
}

/** 掌握状态 → 颜色（与状态语义色板呼应：待复习橙、已掌握绿） */
export const QA_STATUS_COLORS: Record<QaStatus, string> = {
  learning: '#D97706',
  mastered: '#15803D',
}