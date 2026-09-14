import type { ApplicationStatus, EventType, RoundResult, RoundType } from './types'

/** 状态 → 中文标签（rejected/declined 为废弃状态，仅老数据展示兼容） */
export const STATUS_LABELS: Record<ApplicationStatus, string> & Record<string, string> = {
  screening: '初筛',
  assessment: '测评',
  written_test: '笔试',
  interviewing: '面试',
  offer: 'Offer',
  rejected: '挂了',
  declined: '已拒绝',
}

/** 状态 → 颜色（标签与图表共用同一色板；绿/橙/红加深以通过色盲模拟区分度校验） */
export const STATUS_COLORS: Record<ApplicationStatus, string> & Record<string, string> = {
  screening: '#3B82F6',
  assessment: '#0D9488',
  written_test: '#D97706',
  interviewing: '#8B5CF6',
  offer: '#15803D',
  rejected: '#DC2626',
  declined: '#6B7280',
}

/** 状态列表（保持流转顺序） */
export const STATUS_ORDER: ApplicationStatus[] = [
  'screening',
  'assessment',
  'written_test',
  'interviewing',
  'offer',
]

/** 轮次类型 → 要求的投递状态（null = 不限）；硬约束：状态没到位不能加对应轮次 */
export const ROUND_TYPE_STATUS: Record<RoundType, ApplicationStatus | null> = {
  assessment: 'assessment',
  written_test: 'written_test',
  ai: 'interviewing',
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

/** Base 常驻选项（4 大直辖市 + 江浙皖省会 + 成都/深圳/苏州/广州），其余城市可自由输入 */
export const BASE_OPTIONS: string[] = [
  '北京',
  '上海',
  '天津',
  '南京',
  '杭州',
  '合肥',
  '成都',
  '深圳',
  '苏州',
  '广州',
]

/** 流程轮次类型 → 中文标签 */
export const ROUND_TYPE_LABELS: Record<RoundType, string> = {
  assessment: '测评',
  written_test: '笔试',
  ai: 'AI面试',
  first: '一面',
  second: '二面',
  third: '三面',
  hr: 'HR面',
  final: '终面',
  other: '其他',
}

/** 轮次结果 → 中文标签（accepted / rejected_offer 仅 Offer 态展示） */
export const RESULT_LABELS: Record<RoundResult, string> = {
  not_started: '未开始',
  completed: '已完成',
  not_attended: '未参加',
  passed: '通过',
  failed: '未通过',
  accepted: '接受',
  rejected_offer: '拒绝',
}

/** 轮次结果 → 颜色 */
export const RESULT_COLORS: Record<RoundResult, string> = {
  not_started: '#9CA3AF',
  completed: '#3B82F6',
  not_attended: '#6B7280',
  passed: '#22C55E',
  failed: '#EF4444',
  accepted: '#15803D',
  rejected_offer: '#6B7280',
}

/** 非 Offer 态可选的结果（未参加 = 已完成的对立面：跳过 / 放弃该轮） */
export const NORMAL_RESULT_OPTIONS: RoundResult[] = [
  'not_started',
  'completed',
  'not_attended',
  'passed',
  'failed',
]

/** Offer 态可选的结果（仅接受 / 拒绝） */
export const OFFER_RESULT_OPTIONS: RoundResult[] = ['rejected_offer', 'accepted']

/** 自定义日程类型 → 中文标签 */
export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  talk: '宣讲会',
  other: '其他',
}