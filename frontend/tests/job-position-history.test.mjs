import { test } from 'node:test'
import assert from 'node:assert/strict'
import { currentResult, latestRound, resultBucket } from '../src/modules/jobs/selectors.ts'
import { groupPositionHistory, groupResultChanges } from '../src/modules/jobs/history.ts'

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

test('同一代旧数据中，另一岗位与未知岗位都不作为当前结果；明确关联可恢复归属', () => {
  const application = { position: '岗位 B', positionVersion: 1, status: 'interviewing', rounds: [
    { id: 1, position: '岗位 A', positionVersion: 1, result: 'failed' },
    { id: 2, position: null, positionVersion: 1, result: 'completed' },
  ] }
  assert.equal(latestRound(application), null)
  application.statusHistory = [{ id: 10, position: '岗位 B', positionVersion: 1 }]
  application.rounds[1].statusHistoryId = 10
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

const stage = (id, position, positionVersion, status = 'screening') => ({ id, position, positionVersion, status, changedAt: `2026-10-${String(id).padStart(2, '0')}T10:00:00` })
const round = (id, position, positionVersion, statusHistoryId = id) => ({ id, position, positionVersion, statusHistoryId, result: 'failed' })
const result = (id, position, positionVersion, statusHistoryId = id) => ({ id, roundId: id, position, positionVersion, statusHistoryId, status: 'screening', toResult: 'failed', changedAt: '2026-10-20T10:00:00' })
const application = (values = {}) => ({ position: '岗位 B', positionVersion: 2, status: 'screening', rounds: [], statusHistory: [], resultHistory: [], ...values })

test('岗位分组将 A → B → A 保留为三次流程，当前岗位优先且各组包含自己的轮次、状态和结果', () => {
  const rows = groupPositionHistory(application({
    position: '岗位 A', positionVersion: 3,
    rounds: [round(1, '岗位 A', 1), round(2, '岗位 B', 2), round(3, '岗位 A', 3)],
    statusHistory: [stage(1, '岗位 A', 1), stage(2, '岗位 B', 2), stage(3, '岗位 A', 3)],
    resultHistory: [result(1, '岗位 A', 1), result(2, '岗位 B', 2), result(3, '岗位 A', 3)],
  }))
  assert.deepEqual(rows.map(row => [row.position, row.positionVersion, row.isCurrent]), [['岗位 A', 3, true], ['岗位 B', 2, false], ['岗位 A', 1, false]])
  for (const row of rows) {
    assert.deepEqual(row.rounds.map(item => item.id), [row.positionVersion])
    assert.deepEqual(row.statusHistory.map(item => item.id), [row.positionVersion])
    assert.deepEqual(row.resultGroups.get(row.positionVersion).map(item => item.id), [row.positionVersion])
    assert.equal(row.unassignedResults.length, 0)
  }
})

test('旧记录在同一代次补录为不同岗位后分别展示，当前岗位即使没有记录也保留入口', () => {
  const rows = groupPositionHistory(application({
    positionVersion: 1,
    rounds: [round(1, '岗位 A', 1)], statusHistory: [stage(1, '岗位 A', 1)], resultHistory: [result(1, '岗位 A', 1)],
  }))
  assert.deepEqual(rows.map(row => [row.position, row.isCurrent]), [['岗位 B', true], ['岗位 A', false]])
  assert.equal(rows[0].rounds.length, 0)
  assert.deepEqual(rows[1].resultHistory.map(item => item.id), [1])
})

test('缺少岗位快照的旧记录单独展示，不猜测为当前岗位', () => {
  const rows = groupPositionHistory(application({
    positionVersion: 1,
    rounds: [round(1, null, 1)], statusHistory: [stage(1, null, 1)], resultHistory: [result(1, null, 1)],
  }))
  assert.deepEqual(rows.map(row => [row.position, row.isCurrent]), [['岗位 B', true], [null, false]])
  assert.deepEqual(rows[1].rounds.map(item => item.id), [1])
  assert.deepEqual(rows[1].resultGroups.get(1).map(item => item.id), [1])
})

test('只有结果、没有轮次或阶段的岗位仍有独立分组，结果不丢失', () => {
  const rows = groupPositionHistory(application({ resultHistory: [result(1, '岗位 A', 1, null)] }))
  assert.equal(rows.length, 2)
  assert.equal(rows[1].position, '岗位 A')
  assert.deepEqual(rows[1].unassignedResults.map(item => item.id), [1])
  assert.equal(rows[1].rounds.length, 0)
  assert.equal(rows[1].statusHistory.length, 0)
})

test('缺失名称但有明确阶段关联的轮次和结果在该岗位下展示，原快照保持不变', () => {
  const input = application({ rounds: [round(1, null, 1)], statusHistory: [stage(1, '岗位 A', 1)], resultHistory: [result(1, null, 1)] })
  const original = structuredClone(input)
  const rows = groupPositionHistory(input)
  assert.deepEqual(rows.map(row => row.position), ['岗位 B', '岗位 A'])
  assert.deepEqual(rows[1].rounds.map(item => item.id), [1])
  assert.deepEqual(rows[1].resultGroups.get(1).map(item => item.id), [1])
  assert.deepEqual(input, original)
})

test('快照与明确阶段关联冲突时不跨岗位挂载，保留为本岗位未归属结果', () => {
  const rows = groupPositionHistory(application({
    statusHistory: [stage(1, '岗位 A', 1), stage(2, '岗位 B', 2)],
    resultHistory: [result(1, '岗位 B', 2, 1)],
  }))
  assert.equal(rows[0].resultGroups.size, 0)
  assert.deepEqual(rows[0].unassignedResults.map(item => item.id), [1])
  assert.equal(rows[1].resultHistory.length, 0)
})

test('每个分组内状态按时间和编号稳定排列，不改变输入数组或轮次原顺序', () => {
  const input = application({ positionVersion: 1, rounds: [round(2, '岗位 B', 1), round(1, '岗位 B', 1)], statusHistory: [stage(2, '岗位 B', 1, 'interviewing'), stage(1, '岗位 B', 1)] })
  const original = structuredClone(input)
  const rows = groupPositionHistory(input)
  assert.deepEqual(rows[0].statusHistory.map(item => item.id), [1, 2])
  assert.deepEqual(rows[0].rounds.map(item => item.id), [2, 1])
  assert.equal(rows[0].status, 'screening')
  assert.deepEqual(input, original)
})

test('结果缺失名称且阶段关联冲突时，仍随明确所属轮次留在原岗位下', () => {
  const rows = groupPositionHistory(application({
    positionVersion: 1, rounds: [round(1, '岗位 A', 1)],
    statusHistory: [stage(1, '岗位 A', 1), stage(2, '岗位 B', 1)],
    resultHistory: [result(1, null, 1, 2)],
  }))
  assert.equal(rows[0].position, '岗位 B')
  assert.equal(rows[0].resultHistory.length, 0)
  assert.deepEqual(rows[1].unassignedResults.map(item => item.id), [1])
})
