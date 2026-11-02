import type { Application, InterviewRound, RoundResultChange, StatusHistory } from './types'

export const recordedPosition = (position?: string | null) => position?.trim() || null

/** 旧版空快照沿用同一次流程的唯一已知岗位；名称有冲突时只采用明确关联。 */
export function positionResolution(application: Application) {
  const names = new Map<number, Set<string>>()
  const add = (version: number, position?: string | null) => {
    const name = recordedPosition(position)
    if (!name) return
    const values = names.get(version) ?? new Set<string>()
    values.add(name)
    names.set(version, values)
  }
  for (const item of [...application.statusHistory ?? [], ...application.rounds ?? [], ...application.resultHistory ?? []]) add(item.positionVersion ?? 1, item.position)
  if (application.hasCurrentPosition !== false) add(application.positionVersion ?? 1, application.position)
  const stages = new Map((application.statusHistory ?? []).map(item => [item.id, item]))
  const rounds = new Map((application.rounds ?? []).map(item => [item.id, item]))
  const resolve = (version: number, position?: string | null, linked?: string | null): string | null => {
    const values = names.get(version)
    return recordedPosition(position) ?? linked ?? (values?.size === 1 ? [...values][0]! : null)
  }
  const compatible = (left: InterviewRound | RoundResultChange, right: InterviewRound | StatusHistory) =>
    (left.positionVersion ?? 1) === (right.positionVersion ?? 1)
    && (!recordedPosition(left.position) || !recordedPosition(right.position) || recordedPosition(left.position) === recordedPosition(right.position))
  const stagePosition = (item: StatusHistory) => resolve(item.positionVersion ?? 1, item.position)
  const roundPosition = (item: InterviewRound) => {
    const stage = stages.get(item.statusHistoryId!)
    return resolve(item.positionVersion ?? 1, item.position, stage && compatible(item, stage) ? stagePosition(stage) : null)
  }
  const resultPosition = (item: RoundResultChange) => {
    const round = rounds.get(item.roundId), stage = stages.get(item.statusHistoryId!)
    const linked = round && compatible(item, round) ? roundPosition(round) : null
    return resolve(item.positionVersion ?? 1, item.position, linked ?? (stage && compatible(item, stage) ? stagePosition(stage) : null))
  }
  return { stagePosition, roundPosition, resultPosition }
}
