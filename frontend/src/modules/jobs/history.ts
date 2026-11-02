import type { Application, ApplicationStatus, InterviewRound, RoundResultChange, StatusHistory } from './types'

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

const recordedPosition = (position: string | null) => position?.trim() || null
const groupKey = (version: number, position: string | null) => JSON.stringify([version, recordedPosition(position)])
const compatible = (left: { position: string | null; positionVersion: number }, right: { position: string | null; positionVersion: number }) =>
  (left.positionVersion ?? 1) === (right.positionVersion ?? 1)
  && (!recordedPosition(left.position) || !recordedPosition(right.position) || recordedPosition(left.position) === recordedPosition(right.position))

/** 按岗位流程组织详情；同名再次投递仍独立，缺失岗位不使用当前岗位猜测填充。 */
export function groupPositionHistory(application: Application): PositionHistoryGroup[] {
  const currentVersion = application.positionVersion ?? 1
  const currentKey = groupKey(currentVersion, application.position)
  const groups = new Map<string, PositionHistoryGroup>()
  const stages = new Map(application.statusHistory.map(row => [row.id, row]))
  const rounds = new Map(application.rounds.map(row => [row.id, row]))
  const roundGroups = new Map<number, PositionHistoryGroup>()
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
  ensure(currentVersion, application.position)

  for (const stage of application.statusHistory) {
    ensure(stage.positionVersion ?? 1, stage.position).statusHistory.push(stage)
  }
  for (const round of application.rounds) {
    const stage = round.statusHistoryId == null ? undefined : stages.get(round.statusHistoryId)
    // 仅缺失岗位且有同一流程的明确阶段关联时，沿用该阶段的分组，不修改快照。
    const position = recordedPosition(round.position) ?? (stage && compatible(round, stage) ? stage.position : null)
    const group = ensure(round.positionVersion ?? 1, position)
    group.rounds.push(round)
    roundGroups.set(round.id, group)
  }
  for (const result of application.resultHistory) {
    const round = rounds.get(result.roundId)
    const stage = result.statusHistoryId == null ? undefined : stages.get(result.statusHistoryId)
    const linkedGroup = !recordedPosition(result.position) && round && compatible(result, round)
      ? roundGroups.get(round.id) : undefined
    const position = recordedPosition(result.position) ?? linkedGroup?.position ?? (stage && compatible(result, stage) ? stage.position : null)
    const group = ensure(result.positionVersion ?? 1, position)
    group.resultHistory.push(result)
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
