import type { Application } from './types'

export type ListApplication = Application & { displayIsCurrent: boolean; displayStatusRecorded: boolean }

/** 仅为列表和汇总生成视图数据，编辑公司时仍使用原始投递，不把投影保存回去。 */
export function primaryApplication(application: Application): ListApplication {
  const primary = application.primaryPosition
  if (primary === undefined) return { ...application, displayIsCurrent: true, displayStatusRecorded: application.hasCurrentPosition !== false }
  if (!primary) return { ...application, position: null, hasCurrentPosition: false, offerDecision: null,
    rounds: [], statusHistory: [], resultHistory: [], displayIsCurrent: false, displayStatusRecorded: false }
  const roundIds = new Set(primary.roundIds), statusIds = new Set(primary.statusHistoryIds), resultIds = new Set(primary.resultHistoryIds)
  return { ...application, position: primary.position, positionVersion: primary.positionVersion,
    status: primary.status ?? 'screening', hasCurrentPosition: true, offerDecision: primary.offerDecision,
    rounds: application.rounds.filter(item => roundIds.has(item.id)),
    statusHistory: application.statusHistory.filter(item => statusIds.has(item.id)),
    resultHistory: application.resultHistory.filter(item => resultIds.has(item.id)),
    displayIsCurrent: primary.isCurrent, displayStatusRecorded: primary.status !== null }
}
