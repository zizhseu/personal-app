import type { Application, InterviewRound, RoundResult } from './types'

/** 最新轮次按创建顺序判断；rounds 数组在详情中可能按计划时间排序。 */
export function latestRound(application: Application): InterviewRound | null {
  return application.rounds.length
    ? application.rounds.reduce((latest, round) => (round.id > latest.id ? round : latest))
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
