import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createScheduleGroups } from '../src/modules/jobs/schedule.ts'

const NOW = new Date('2026-11-06T08:00:00').getTime()
const round = (id, values = {}) => ({
  id, position: '测试岗位', positionVersion: 1, roundType: 'written_test', result: 'not_started',
  startAt: '2026-11-06T09:00:00', scheduledAt: '2026-11-09T09:00:00', resultChangedAt: null,
  ...values,
})
const application = rounds => ({ id: 1, company: '示例公司', rounds })
const event = (id, eventTime) => ({ id, title: '自定义日程', eventType: 'talk', eventTime, location: null, applicationId: null })

test('日程显示开始时间，即使截止在三天后，源数据也保持原值', () => {
  const source = [application([round(1)])]
  const original = structuredClone(source)
  const item = createScheduleGroups(source, [], NOW).todo[0]
  assert.equal(item.time, '11-06 09:00')
  assert.equal(item.startAt, '2026-11-06T09:00:00')
  assert.equal(item.deadlineAt, '2026-11-09T09:00:00')
  assert.deepEqual(source, original)
})

test('待办轮次和自定义日程统一按开始时间排列，截止先后不影响顺序', () => {
  const source = [application([
    round(1),
    round(2, { startAt: '2026-11-06T10:00:00', scheduledAt: '2026-11-06T11:00:00' }),
  ])]
  const groups = createScheduleGroups(source, [event(1, '2026-11-06T09:30:00')], NOW)
  assert.deepEqual(groups.todo.map(item => item.key), ['round-1', 'event-1', 'round-2'])
})

test('已办保留原定开始时间，结果更新时间不覆盖显示或排序', () => {
  const source = [application([
    round(1, { startAt: '2026-11-04T09:00:00', scheduledAt: '2026-11-04T12:00:00', result: 'completed', resultChangedAt: '2026-11-06T07:30:00' }),
    round(2, { startAt: '2026-11-05T09:00:00', scheduledAt: '2026-11-05T12:00:00', result: 'passed', resultChangedAt: '2026-11-05T12:00:00' }),
  ])]
  const groups = createScheduleGroups(source, [], NOW)
  assert.deepEqual(groups.done.map(item => item.key), ['round-2', 'round-1'])
  assert.deepEqual(groups.done.map(item => item.time), ['11-05 09:00', '11-04 09:00'])
})

test('过期事项也按开始时间显示和排序，期限仍由截止时间判定', () => {
  const source = [application([
    round(1, { startAt: '2026-11-03T09:00:00', scheduledAt: '2026-11-05T09:00:00' }),
    round(2, { startAt: '2026-11-04T09:00:00', scheduledAt: '2026-11-04T10:00:00' }),
    round(3, { startAt: '2026-11-05T09:00:00', scheduledAt: '2026-11-07T09:00:00' }),
  ])]
  const groups = createScheduleGroups(source, [], NOW)
  assert.deepEqual(groups.expired.map(item => item.key), ['round-2', 'round-1'])
  assert.equal(groups.expired[0].time, '11-04 09:00')
  assert.equal(groups.todo[0].key, 'round-3')
})

test('旧记录只有截止时间时明确提示补充开始时间，并排在已知开始时间之后', () => {
  const groups = createScheduleGroups([application([
    round(1, { startAt: null, scheduledAt: '2026-11-06T10:00:00' }),
    round(2),
  ])], [], NOW)
  assert.deepEqual(groups.todo.map(item => item.key), ['round-2', 'round-1'])
  assert.equal(groups.todo[1].time, '开始时间待补充')
  assert.equal(groups.todo[1].startAt, null)
})

test('只有开始时间的旧记录也能归入日程，初筛和未安排时间的轮次继续排除', () => {
  const groups = createScheduleGroups([application([
    round(1, { startAt: '2026-11-05T09:00:00', scheduledAt: null }),
    round(2, { roundType: 'screening' }),
    round(3, { startAt: null, scheduledAt: null }),
  ])], [], NOW)
  assert.deepEqual(groups.expired.map(item => item.key), ['round-1'])
  assert.equal(groups.todo.length, 0)
  assert.equal(groups.done.length, 0)
})

test('当天已过的期限及时归入过期，时钟推进后分组随之更新', () => {
  const source = [application([round(1, { startAt: '2026-11-06T07:00:00', scheduledAt: '2026-11-06T08:01:00' })])]
  const upcoming = createScheduleGroups(source, [], NOW)
  const later = createScheduleGroups(source, [], NOW + 2 * 60_000)
  assert.equal(upcoming.todo[0].key, 'round-1')
  assert.equal(later.expired[0].key, 'round-1')
  const events = createScheduleGroups([], [event(1, '2026-11-06T07:59:00'), event(2, '2026-11-06T08:01:00')], NOW)
  assert.equal(events.done[0].time, '11-06 07:59')
  assert.equal(events.todo[0].time, '11-06 08:01')
})

test('所有已记录结果均归入已办，支持既有结果枚举', () => {
  const results = ['completed', 'passed', 'failed', 'not_attended', 'accepted', 'rejected_offer']
  const groups = createScheduleGroups([application(results.map((result, index) => round(index + 1, { result })))], [], NOW)
  assert.equal(groups.done.length, results.length)
  assert.equal(groups.todo.length, 0)
  assert.equal(groups.expired.length, 0)
})
