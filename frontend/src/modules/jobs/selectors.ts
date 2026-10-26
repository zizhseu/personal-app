import type { Application, InterviewRound, RoundResult } from './types'

export const positionLabel = (position?: string | null) => position?.trim() || '岗位未记录'

export function isCurrentRound(round: InterviewRound, application: Application): boolean {
  return (round.positionVersion ?? 1) === (application.positionVersion ?? 1)
    && (round.position == null || round.position === application.position)
}

export function currentRounds(application: Application): InterviewRound[] {
  return application.rounds.filter(round => isCurrentRound(round, application))
}

/** 最新轮次按创建顺序判断；rounds 数组在详情中可能按计划时间排序。 */
export function latestRound(application: Application): InterviewRound | null {
  const rounds = currentRounds(application)
  return rounds.length
    ? rounds.reduce((latest, round) => (round.id > latest.id ? round : latest))
    : null
}

/** 与投递列表的「结果」列统一口径：Offer 看决定，其他状态看最新轮次。 */
export function currentResult(application: Application): RoundResult | null {
  return application.status === 'offer'
    ? application.offerDecision
    : latestRound(application)?.result ?? null
}

export type ResultBucket = RoundResult | 'undecided' | 'unrecorded'

export function resultBucket(application: Application): ResultBucket {
  const result = currentResult(application)
  if (result) return result
  return application.status === 'offer' ? 'undecided' : 'unrecorded'
}
