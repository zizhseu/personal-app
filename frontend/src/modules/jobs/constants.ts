import type { ApplicationStatus, EventType, RoundResult, RoundType } from './types'

/** 状态 → 中文标签 */
export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  applied: '投递中',
  viewed: '已查看',
  assessment: '测评',
  written_test: '笔试',
  interviewing: '面试中',
  offer: 'Offer',
  rejected: '挂了',
  declined: '已拒绝',
}

/** 状态 → 颜色（标签与图表共用同一色板；绿/橙/红加深以通过色盲模拟区分度校验） */
export const STATUS_COLORS: Record<ApplicationStatus, string> = {
  applied: '#3B82F6',
  viewed: '#94A3B8',
  assessment: '#0D9488',
  written_test: '#D97706',
  interviewing: '#8B5CF6',
  offer: '#15803D',
  rejected: '#DC2626',
  declined: '#6B7280',
}

/** 状态列表（保持流转顺序） */
export const STATUS_ORDER: ApplicationStatus[] = [
  'applied',
  'viewed',
  'assessment',
  'written_test',
  'interviewing',
  'offer',
  'rejected',
  'declined',
]

/** 挂的阶段 → 显示标签（状态为「挂了」时替代显示，由后端按挂之前的状态自动推断） */
export const REJECT_STAGE_LABELS: Record<string, string> = {
  resume: '简历挂',
  assessment: '测评挂',
  written_test: '笔试挂',
  first: '一面挂',
  second: '二面挂',
  third: '三面挂',
  hr: 'HR面挂',
  final: '终面挂',
  interview: '面试挂',
}

/** 轮次类型 → 要求的投递状态（null = 不限）；硬约束：状态没到位不能加对应轮次 */
export const ROUND_TYPE_STATUS: Record<RoundType, ApplicationStatus | null> = {
  assessment: 'assessment',
  written_test: 'written_test',
  first: 'interviewing',
  second: 'interviewing',
  third: 'interviewing',
  hr: 'interviewing',
  final: 'interviewing',
  other: null,
}

/** 招聘渠道固定选项（单选） */
export const CHANNELS: string[] = [
  '官网',
  '内推',
  '牛客',
  'BOSS直聘',
  '智联招聘',
  '前程无忧',
  '猎聘',
  '拉勾',
  '实习僧',
  '其他',
]

/** 流程轮次类型 → 中文标签 */
export const ROUND_TYPE_LABELS: Record<RoundType, string> = {
  assessment: '测评',
  written_test: '笔试',
  first: '一面',
  second: '二面',
  third: '三面',
  hr: 'HR面',
  final: '终面',
  other: '其他',
}

/** 轮次结果 → 中文标签 */
export const RESULT_LABELS: Record<RoundResult, string> = {
  pending: '待定',
  passed: '通过',
  failed: '未通过',
}

/** 轮次结果 → 颜色 */
export const RESULT_COLORS: Record<RoundResult, string> = {
  pending: '#94A3B8',
  passed: '#22C55E',
  failed: '#EF4444',
}

/** 自定义日程类型 → 中文标签 */
export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  talk: '宣讲会',
  other: '其他',
}