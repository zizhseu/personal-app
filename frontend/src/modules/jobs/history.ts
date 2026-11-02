import type { Application, ApplicationStatus, InterviewRound, RoundResultChange, StatusHistory } from './types'
import { positionResolution, recordedPosition } from './positionResolution.ts'

/** 新记录按阶段标识归属；兼容旧记录时同时限制岗位代次、状态和时间。 */
export function groupResultChanges(history: StatusHistory[], results: RoundResultChange[]) {
  const groups = new Map<number, RoundResultChange[]>(), unassigned: RoundResultChange[] = []
  for (const result of results) {
    let stage = history.find(row => row.id === result.statusHistoryId)
    if (!stage) {
      const candidates = history.filter(row => row.status === result.status
        && (row.positionVersion ?? 1) === (result.positionVersion ?? 1)
        && (!row.position || !result.position || row.position === result.position)
        && new Date(row.changedAt).getTime() <= new Date(result.changedAt).getTime())
      stage = candidates.sort((left, right) => new Date(right.changedAt).getTime() - new Date(left.changedAt).getTime() || right.id - left.id)[0]
    }
    if (!stage) { unassigned.push(result); continue }
    const rows = groups.get(stage.id) ?? []
    rows.push(result)
    groups.set(stage.id, rows)
  }
  return { groups, unassigned }
}

export interface PositionHistoryGroup {
  key: string
  position: string | null
  positionVersion: number
  isCurrent: boolean
  status: ApplicationStatus | null
  rounds: InterviewRound[]
  statusHistory: StatusHistory[]
  resultHistory: RoundResultChange[]
  resultGroups: Map<number, RoundResultChange[]>
  unassignedResults: RoundResultChange[]
}

const groupKey = (version: number, position: string | null) => JSON.stringify([version, recordedPosition(position)])

/** 同名再次投递独立；旧版空快照沿同流程唯一名称归组，不改写原始数据。 */
export function groupPositionHistory(application: Application): PositionHistoryGroup[] {
  const currentVersion = application.positionVersion ?? 1
  const currentKey = groupKey(currentVersion, application.position)
  const groups = new Map<string, PositionHistoryGroup>()
  const stages = new Map(application.statusHistory.map(row => [row.id, row]))
  const resolution = positionResolution(application)
  const ensure = (version: number, position: string | null) => {
    const key = groupKey(version, position)
    let group = groups.get(key)
    if (!group) {
      group = {
        key, position: recordedPosition(position), positionVersion: version, isCurrent: key === currentKey,
        status: null, rounds: [], statusHistory: [], resultHistory: [], resultGroups: new Map(), unassignedResults: [],
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
    const stageIds = new Set(group.statusHistory.map(stage => stage.id))
    // 明确关联到另一岗位的异常快照保留在本组待归属，不回退匹配到本组的其他阶段。
    const conflicting = group.resultHistory.filter(result => result.statusHistoryId != null && stages.has(result.statusHistoryId) && !stageIds.has(result.statusHistoryId))
    const conflictingIds = new Set(conflicting.map(result => result.id))
    const results = groupResultChanges(group.statusHistory, group.resultHistory.filter(result => !conflictingIds.has(result.id)))
    const unassignedIds = new Set([...conflicting, ...results.unassigned].map(result => result.id))
    group.resultGroups = results.groups
    group.unassignedResults = group.resultHistory.filter(result => unassignedIds.has(result.id))
    group.status = group.isCurrent ? application.status : group.statusHistory.at(-1)?.status ?? group.resultHistory.at(-1)?.status ?? null
  }
  return [...groups.values()].sort((left, right) => Number(right.isCurrent) - Number(left.isCurrent)
    || right.positionVersion - left.positionVersion || Number(left.position == null) - Number(right.position == null))
}
