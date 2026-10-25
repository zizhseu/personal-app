import { test } from 'node:test'
import assert from 'node:assert/strict'
import { setImmediate } from 'node:timers/promises'
import { createAutosave } from '../src/modules/coding/autosave.ts'

function setup(t, overrides = {}) {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let form = { title: '手撕题', code: '原始代码' }
  let stored = JSON.stringify(form)
  const writes = [], saving = [], errors = []
  const saver = createAutosave({
    read: () => structuredClone(form),
    dirty: () => JSON.stringify(form) !== stored,
    valid: () => !!form.title.trim(),
    write: async snapshot => { writes.push(snapshot); stored = JSON.stringify(snapshot) },
    saving: value => saving.push(value),
    failed: error => { errors.push(error); return null },
    ...overrides,
  })
  t.after(() => saver.dispose())
  return { saver, writes, saving, errors,
    change: values => { form = { ...form, ...values }; saver.schedule() },
    commit: snapshot => { stored = JSON.stringify(snapshot) },
    current: () => form, stored: () => JSON.parse(stored),
  }
}

test('停止输入一秒才保存，连续输入只提交最后的内容', async t => {
  const ctx = setup(t)
  ctx.change({ code: '第一段' })
  t.mock.timers.tick(999)
  await setImmediate()
  assert.equal(ctx.writes.length, 0)
  ctx.change({ code: '完整代码' })
  t.mock.timers.tick(999)
  await setImmediate()
  assert.equal(ctx.writes.length, 0)
  t.mock.timers.tick(1)
  await setImmediate()
  assert.equal(ctx.writes.length, 1)
  assert.equal(ctx.writes[0].code, '完整代码')
  assert.deepEqual(ctx.saving, [true, false])
})

test('慢请求期间可继续输入，后续保存串行写入最新内容', async t => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  let active = 0, maxActive = 0
  const ctx = setup(t, { write: async snapshot => {
    ctx.writes.push(snapshot)
    maxActive = Math.max(maxActive, ++active)
    if (ctx.writes.length === 1) await gate
    ctx.commit(snapshot)
    active--
  } })
  ctx.change({ code: '第一版' })
  t.mock.timers.tick(1000)
  await setImmediate()
  ctx.change({ code: '保存中继续输入的第二版' })
  t.mock.timers.tick(1000)
  await setImmediate()
  assert.equal(ctx.writes.length, 1)
  release()
  await setImmediate()
  assert.equal(ctx.current().code, '保存中继续输入的第二版')
  t.mock.timers.tick(0)
  await setImmediate()
  assert.equal(ctx.writes.length, 2)
  assert.equal(ctx.stored().code, '保存中继续输入的第二版')
  assert.equal(maxActive, 1)
})

test('离开时立即保存，并等待保存期间产生的最新修改', async t => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  const ctx = setup(t, { write: async snapshot => {
    ctx.writes.push(snapshot)
    if (ctx.writes.length === 1) await gate
    ctx.commit(snapshot)
  } })
  ctx.change({ code: '第一版' })
  t.mock.timers.tick(1000)
  await setImmediate()
  ctx.change({ code: '离开前的最终版' })
  const flushing = ctx.saver.flush()
  release()
  assert.equal(await flushing, true)
  assert.equal(ctx.stored().code, '离开前的最终版')
  assert.equal(ctx.writes.length, 2)
})

test('网络失败保留输入，按照指定间隔重试', async t => {
  const ctx = setup(t, {
    write: async snapshot => {
      ctx.writes.push(snapshot)
      if (ctx.writes.length === 1) throw new Error('暂时离线')
      ctx.commit(snapshot)
    },
    failed: error => { ctx.errors.push(error); return 3000 },
  })
  ctx.change({ code: '尚未写入的内容' })
  t.mock.timers.tick(1000)
  await setImmediate()
  assert.equal(ctx.errors.length, 1)
  assert.equal(ctx.current().code, '尚未写入的内容')
  assert.equal(ctx.stored().code, '原始代码')
  t.mock.timers.tick(2999)
  await setImmediate()
  assert.equal(ctx.writes.length, 1)
  t.mock.timers.tick(1)
  await setImmediate()
  assert.equal(ctx.stored().code, '尚未写入的内容')
})

test('必填项为空时不提交，补齐后自动保存', async t => {
  const ctx = setup(t)
  ctx.change({ title: '', code: '草稿' })
  t.mock.timers.tick(1000)
  assert.equal(await ctx.saver.flush(), false)
  assert.equal(ctx.writes.length, 0)
  ctx.change({ title: '补齐题目名称' })
  t.mock.timers.tick(1000)
  await setImmediate()
  assert.equal(ctx.stored().title, '补齐题目名称')
  assert.equal(ctx.stored().code, '草稿')
})

test('多个立即保存请求合并，不重复创建记录', async t => {
  const ctx = setup(t)
  ctx.change({ code: '新内容' })
  assert.deepEqual(await Promise.all([ctx.saver.flush(), ctx.saver.flush()]), [true, true])
  assert.equal(ctx.writes.length, 1)
  t.mock.timers.tick(10000)
  await setImmediate()
  assert.equal(ctx.writes.length, 1)
})

test('离开工作区后取消尚未开始的定时保存', async t => {
  const ctx = setup(t)
  ctx.change({ code: '未提交' })
  ctx.saver.dispose()
  t.mock.timers.tick(10000)
  await setImmediate()
  assert.equal(ctx.writes.length, 0)
})
