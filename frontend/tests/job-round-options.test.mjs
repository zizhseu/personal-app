import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ROUND_TYPE_LABELS, ROUND_TYPE_STATUS, OFFER_RESULT_OPTIONS } from '../src/modules/jobs/constants.ts'
import { roundResultOptions, roundTypeOptions } from '../src/modules/jobs/roundOptions.ts'
import { createScheduleGroups } from '../src/modules/jobs/schedule.ts'

const OFFER_TYPES = ['verbal_offer', 'formal_offer', 'tripartite']

test('当前和历史 Offer 岗位只提供口头 Offer、正式 Offer、三方', () => {
  assert.deepEqual(roundTypeOptions('offer'), OFFER_TYPES)
  assert.deepEqual(roundTypeOptions('offer', true), OFFER_TYPES)
  assert.deepEqual(OFFER_TYPES.map(type => ROUND_TYPE_LABELS[type]), ['口头 Offer', '正式 Offer', '三方'])
  assert.ok(OFFER_TYPES.every(type => ROUND_TYPE_STATUS[type] === 'offer'))
})

test('其他当前阶段继续按阶段筛选，Offer 类型只属于 Offer 阶段', () => {
  assert.deepEqual(roundTypeOptions('screening'), ['screening'])
  assert.deepEqual(roundTypeOptions('rescreen'), ['assessment', 'written_test', 'ai', 'other'])
  assert.deepEqual(roundTypeOptions('interviewing'), ['first', 'second', 'third', 'hr', 'final'])
})

test('非 Offer 历史岗位保留跨阶段补录能力，本阶段类型优先', () => {
  const types = roundTypeOptions('rescreen', true)
  assert.deepEqual(types.slice(0, 4), ['assessment', 'written_test', 'ai', 'other'])
  assert.ok(types.includes('first'))
  assert.ok(types.includes('screening'))
  assert.ok(OFFER_TYPES.every(type => !types.includes(type)))
  assert.equal(types.length, 10)
})

test('编辑旧 Offer 轮次时保留原类型，并提供三种新类型供更正', () => {
  assert.deepEqual(roundTypeOptions('offer', false, 'other'), [...OFFER_TYPES, 'other'])
  assert.deepEqual(roundTypeOptions('offer', false, 'formal_offer'), OFFER_TYPES)
})

test('新 Offer 轮次的中性默认结果可见，接受和拒绝保留供用户选择', () => {
  const original = [...OFFER_RESULT_OPTIONS]
  const options = roundResultOptions('offer')
  assert.deepEqual(options, ['rejected_offer', 'accepted', 'not_started'])
  assert.deepEqual(OFFER_RESULT_OPTIONS, original)
  assert.deepEqual(roundResultOptions('offer'), options)
})

test('旧结果保留且不重复，普通阶段沿用原来的五种结果', () => {
  assert.deepEqual(roundResultOptions('offer', 'completed'), ['rejected_offer', 'accepted', 'completed'])
  assert.deepEqual(roundResultOptions('offer', 'accepted'), ['rejected_offer', 'accepted'])
  assert.deepEqual(roundResultOptions('rescreen'), ['not_started', 'completed', 'not_attended', 'passed', 'failed'])
})

test('新 Offer 类型进入日程后均显示对应中文名称和开始时间', () => {
  const application = { id: 1, company: 'Offer 示例', rounds: OFFER_TYPES.map((type, index) => ({
    id: index + 1, position: '示例岗位', roundType: type, result: 'not_started',
    startAt: '2026-11-09T12:00:00', scheduledAt: '2026-11-09T13:00:00',
  })) }
  const groups = createScheduleGroups([application], [], new Date('2026-11-09T10:00:00').getTime())
  assert.deepEqual(groups.todo.map(item => item.typeLabel), ['口头 Offer', '正式 Offer', '三方'])
  assert.ok(groups.todo.every(item => item.time === '11-09 12:00'))
})
