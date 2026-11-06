import { test } from 'node:test'
import assert from 'node:assert/strict'
import { positionStatusPayload } from '../src/modules/jobs/positionStatus.ts'

const application = () => ({
  position: '当前岗位', positionVersion: 3,
  statusHistory: [
    { id: 40, position: '目标岗位', positionVersion: 1, changedAt: '2026-11-05T10:00:00' },
    { id: 41, position: '目标岗位', positionVersion: 1, changedAt: '2026-11-05T10:00:00' },
    { id: 90, position: '当前岗位', positionVersion: 3, changedAt: '2026-11-06T10:00:00' },
  ],
})
const target = () => ({ position: '目标岗位', positionVersion: 1, status: 'rescreen', statusHistoryIds: [40, 41] })

test('修改非主要旧岗位时，目标版本与当前并发校验版本分别取值，状态历史限制到该岗位', () => {
  const source = application()
  const before = structuredClone(source)
  const payload = positionStatusPayload(source, target(), 'interviewing')
  assert.deepEqual(payload, {
    position: '目标岗位', positionVersion: 1, expectedPositionVersion: 3,
    status: 'interviewing', expectedStatus: 'rescreen', expectedStatusHistoryId: 41,
  })
  assert.deepEqual(source, before)
})

test('没有状态历史的岗位也可以明确设置状态，未知名称保持空值', () => {
  const payload = positionStatusPayload(application(), { ...target(), position: null, status: null, statusHistoryIds: [] }, 'screening')
  assert.equal(payload.position, null)
  assert.equal(payload.expectedStatus, null)
  assert.equal(payload.expectedStatusHistoryId, null)
})

test('旧数据的阶段按时间和编号选最新记录，而非使用其他岗位的最新记录', () => {
  const source = application()
  source.statusHistory[0].changedAt = '2026-11-05T11:00:00'
  assert.equal(positionStatusPayload(source, target(), 'offer').expectedStatusHistoryId, 40)
})

test('早期废弃状态作为旧值送回校验，用户仍可选择现行状态', () => {
  const payload = positionStatusPayload(application(), { ...target(), status: 'rejected' }, 'rescreen')
  assert.equal(payload.expectedStatus, 'rejected')
  assert.equal(payload.status, 'rescreen')
})
