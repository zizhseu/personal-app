import type { RoundResultChange, StatusHistory } from './types'

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
