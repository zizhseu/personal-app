import type { Application, ApplicationStatus, PositionStatusPayload, PositionSummary } from './types'

/** 并发校验使用原始投递版本，状态记录只取目标岗位的成员。 */
export function positionStatusPayload(
  application: Application,
  position: PositionSummary,
  status: ApplicationStatus,
): PositionStatusPayload {
  const stageIds = new Set(position.statusHistoryIds)
  const stages = application.statusHistory.filter(stage => stageIds.has(stage.id))
  stages.sort((left, right) => left.changedAt.localeCompare(right.changedAt) || left.id - right.id)
  return {
    position: position.position,
    positionVersion: position.positionVersion,
    expectedPositionVersion: application.positionVersion,
    status,
    expectedStatus: position.status,
    expectedStatusHistoryId: stages.at(-1)?.id ?? null,
  }
}
