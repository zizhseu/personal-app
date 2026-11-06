import type { Application, ApplicationStatus, InterviewRound, RoundResultChange, StatusHistory } from './types'
import { positionResolution, recordedPosition } from './positionResolution.ts'

export interface PositionHistoryGroup {
  key: string
  position: string | null
  positionVersion: number
  isCurrent: boolean
  isPrimary: boolean
  displayOrder: number
  status: ApplicationStatus | null
  rounds: InterviewRound[]
  statusHistory: StatusHistory[]
  resultHistory: RoundResultChange[]
  roundResults: Map<number, RoundResultChange[]>
  retainedResults: RoundResultChange[]
}

const groupKey = (version: number, position: string | null) => JSON.stringify([version, recordedPosition(position)])

/** 同名再次投递独立；旧版空快照沿同流程唯一名称归组，不改写原始数据。 */
export function groupPositionHistory(application: Application): PositionHistoryGroup[] {
  const currentVersion = application.positionVersion ?? 1
  const currentKey = groupKey(currentVersion, application.position)
  const groups = new Map<string, PositionHistoryGroup>()
  const resolution = positionResolution(application)
  const ensure = (version: number, position: string | null) => {
    const key = groupKey(version, position)
    let group = groups.get(key)
    if (!group) {
      group = {
        key, position: recordedPosition(position), positionVersion: version, isCurrent: key === currentKey,
        isPrimary: false, displayOrder: 0,
        status: null, rounds: [], statusHistory: [], resultHistory: [], roundResults: new Map(), retainedResults: [],
      }
      groups.set(key, group)
    }
    return group
  }
  if (application.hasCurrentPosition !== false) ensure(currentVersion, application.position)

  for (const stage of application.statusHistory) {
    ensure(stage.positionVersion ?? 1, resolution.stagePosition(stage)).statusHistory.push(stage)
  }
  for (const round of application.rounds) {
    ensure(round.positionVersion ?? 1, resolution.roundPosition(round)).rounds.push(round)
  }
  for (const result of application.resultHistory) {
    ensure(result.positionVersion ?? 1, resolution.resultPosition(result)).resultHistory.push(result)
  }
  for (const group of groups.values()) {
    group.statusHistory.sort((left, right) => new Date(left.changedAt).getTime() - new Date(right.changedAt).getTime() || left.id - right.id)
    group.resultHistory.sort((left, right) => new Date(left.changedAt).getTime() - new Date(right.changedAt).getTime() || left.id - right.id)
    const roundIds = new Set(group.rounds.map(round => round.id))
    for (const result of group.resultHistory) {
      if (!roundIds.has(result.roundId)) {
        group.retainedResults.push(result)
        continue
      }
      const changes = group.roundResults.get(result.roundId) ?? []
      changes.push(result)
      group.roundResults.set(result.roundId, changes)
    }
    group.status = group.isCurrent ? application.status : group.statusHistory.at(-1)?.status ?? group.resultHistory.at(-1)?.status ?? null
  }
  const values = [...groups.values()]
  const firstTime = (group: PositionHistoryGroup) => Math.min(...[
    ...group.statusHistory.map(item => item.changedAt), ...group.rounds.map(item => item.createdAt), ...group.resultHistory.map(item => item.changedAt),
  ].filter(Boolean).map(value => new Date(value).getTime()), Infinity)
  values.slice().sort((left, right) => left.positionVersion - right.positionVersion || firstTime(left) - firstTime(right)
    || (left.key < right.key ? -1 : left.key > right.key ? 1 : 0)).forEach((group, index) => {
      const summary = application.positionSummaries?.find(item => groupKey(item.positionVersion, item.position) === group.key)
      group.displayOrder = summary?.displayOrder ?? index + 1
      group.isPrimary = summary?.isPrimary ?? (application.primaryPosition === undefined ? group.isCurrent
        : !!application.primaryPosition && groupKey(application.primaryPosition.positionVersion, application.primaryPosition.position) === group.key)
      if (summary) group.status = summary.status
    })
  return values.sort((left, right) => Number(right.isPrimary) - Number(left.isPrimary) || Number(right.isCurrent) - Number(left.isCurrent)
    || right.positionVersion - left.positionVersion || Number(left.position == null) - Number(right.position == null))
}
