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

/** 标签统一显示顺序（同一组标签在所有页面渲染一致，存储保留用户输入顺序） */
export function sortTags(tags: string[] | null | undefined): string[] {
  return [...(tags ?? [])].sort((a, b) => a.localeCompare(b, 'zh'))
}