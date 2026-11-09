import { NORMAL_RESULT_OPTIONS, OFFER_RESULT_OPTIONS, ROUND_TYPE_LABELS, ROUND_TYPE_STATUS } from './constants.ts'
import type { ApplicationStatus, RoundResult, RoundType } from './types'

/** Offer 岗位按本身状态筛选，其他历史岗位保留跨阶段补录能力。 */
export function roundTypeOptions(status: ApplicationStatus | null | undefined, historical = false, originalType?: RoundType): RoundType[] {
  const all = Object.keys(ROUND_TYPE_LABELS) as RoundType[]
  const allowed = all.filter(type => historical && status !== 'offer'
    ? ROUND_TYPE_STATUS[type] !== 'offer'
    : ROUND_TYPE_STATUS[type] === status)
  if (historical && status !== 'offer') {
    allowed.sort((left, right) =>
      Number(ROUND_TYPE_STATUS[right] === status) - Number(ROUND_TYPE_STATUS[left] === status))
  }
  // 编辑旧记录时保留原类型，用户可主动更正。
  if (originalType && !allowed.includes(originalType)) allowed.push(originalType)
  return allowed
}

/** 新轮次保留中性初始结果，旧结果仍可查看和编辑。 */
export function roundResultOptions(status: ApplicationStatus | null | undefined, originalResult: RoundResult = 'not_started'): RoundResult[] {
  const options = [...(status === 'offer' ? OFFER_RESULT_OPTIONS : NORMAL_RESULT_OPTIONS)]
  if (!options.includes(originalResult)) options.push(originalResult)
  return options
}
