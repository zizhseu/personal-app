import { test } from 'node:test'
import assert from 'node:assert/strict'
import { currentResult, latestRound, resultBucket } from '../src/modules/jobs/selectors.ts'
import { groupResultChanges } from '../src/modules/jobs/history.ts'

test('改投后的当前结果不使用旧岗位失败记录，再回到同名岗位也不串用', () => {
  const application = { position: '岗位 A', positionVersion: 3, status: 'screening', rounds: [
    { id: 1, position: '岗位 A', positionVersion: 1, result: 'failed' },
    { id: 2, position: '岗位 B', positionVersion: 2, result: 'failed' },
  ] }
  assert.equal(latestRound(application), null)
  assert.equal(resultBucket(application), 'unrecorded')
  application.rounds.push({ id: 3, position: '岗位 A', positionVersion: 3, result: 'not_started' })
  assert.equal(currentResult(application), 'not_started')
})

test('同一代旧数据补录为另一个岗位后，不作为当前岗位结果', () => {
  const application = { position: '岗位 B', positionVersion: 1, status: 'interviewing', rounds: [
    { id: 1, position: '岗位 A', positionVersion: 1, result: 'failed' },
    { id: 2, position: null, positionVersion: 1, result: 'completed' },
  ] }
  assert.equal(latestRound(application).id, 2)
  application.rounds.pop()
  assert.equal(currentResult(application), null)
})

test('旧轮次晚补的结果仍归原阶段，不会落到新岗位的同名状态', () => {
  const stages = [
    { id: 1, status: 'screening', position: '岗位 A', positionVersion: 1, changedAt: '2026-10-01T10:00:00' },
    { id: 2, status: 'screening', position: '岗位 B', positionVersion: 2, changedAt: '2026-10-02T10:00:00' },
  ]
  const result = { id: 1, statusHistoryId: 1, status: 'screening', position: '岗位 A', positionVersion: 1, changedAt: '2026-10-03T10:00:00' }
  const { groups, unassigned } = groupResultChanges(stages, [result])
  assert.deepEqual(groups.get(1), [result])
  assert.equal(groups.has(2), false)
  assert.deepEqual(unassigned, [])
})

test('旧结果回退按岗位代次隔离，同一时间用阶段编号稳定归属', () => {
  const stages = [
    { id: 1, status: 'screening', position: '岗位 A', positionVersion: 1, changedAt: '2026-10-01T10:00:00' },
    { id: 2, status: 'screening', position: '岗位 A', positionVersion: 1, changedAt: '2026-10-01T10:00:00' },
    { id: 3, status: 'screening', position: '岗位 A', positionVersion: 3, changedAt: '2026-10-02T10:00:00' },
  ]
  const result = { id: 1, statusHistoryId: null, status: 'screening', position: '岗位 A', positionVersion: 1, changedAt: '2026-10-03T10:00:00' }
  assert.deepEqual(groupResultChanges(stages, [result]).groups.get(2), [result])
})

test('无法归属的结果保持可见，不强行放进其他岗位的阶段', () => {
  const stages = [{ id: 1, status: 'screening', position: '岗位 B', positionVersion: 2, changedAt: '2026-10-01T10:00:00' }]
  const result = { id: 1, statusHistoryId: null, status: 'screening', position: '岗位 A', positionVersion: 1, changedAt: '2026-10-02T10:00:00' }
  const grouped = groupResultChanges(stages, [result])
  assert.equal(grouped.groups.size, 0)
  assert.deepEqual(grouped.unassigned, [result])
})
