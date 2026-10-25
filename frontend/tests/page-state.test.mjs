import { test } from 'node:test'
import assert from 'node:assert/strict'
import { choiceField, createViewMemory, listField, pageField, parseSignature, querySignature, readView, resolveView, textField, writeView } from '../src/shared/state/pageState.ts'

const fields = {
  q: textField(), status: choiceField('', ['', 'learning', 'mastered']),
  tag: listField(), exclude: listField(), page: pageField(),
}
function storage() {
  const items = new Map()
  return { getItem: key => items.get(key) ?? null, setItem: (key, value) => items.set(key, value), items }
}

test('中文、特殊字符及多标签可往返序列化，数组保持完整', () => {
  const values = readView(fields, { q: '银行 & 缓存 / #1', tag: ['a,b', '状态恢复', 'a,b'], exclude: ['并发'], page: '3' })
  const query = writeView(fields, values)
  assert.deepEqual(readView(fields, parseSignature(querySignature(query))), values)
  assert.equal(query.page, '3')
  assert.deepEqual(query.tag, ['a,b', '状态恢复'])
})

test('显式地址优先；空地址恢复记忆；显式默认条件不会复活旧搜索', () => {
  const saved = querySignature({ q: '银行', status: 'learning', page: '4' })
  assert.equal(resolveView(fields, {}, saved).q, '银行')
  assert.equal(resolveView(fields, { q: '邮储银行' }, saved).page, 1)
  assert.equal(resolveView(fields, { q: '邮储银行' }, saved).q, '邮储银行')
  assert.deepEqual(resolveView(fields, { page: '1' }, saved), readView(fields, {}))
  assert.deepEqual(writeView(fields, readView(fields, {})), { page: '1' })
})

test('无效枚举、页码及未知字段不进入恢复状态', () => {
  for (const page of ['0', '-1', '2.5', 'Infinity', '100001', null, {}, 'oops']) {
    const values = readView(fields, { page, status: 'unexpected', token: 'example', record: { code: 'example' } })
    assert.equal(values.page, 1)
    assert.equal(values.status, '')
    assert.deepEqual(Object.keys(writeView(fields, values)), ['page'])
  }
  assert.equal(textField(3).read('abcdef'), 'abc')
  assert.deepEqual(listField(['learning', 'mastered']).read(['learning', null, 'bogus', 'learning']), ['learning'])
})

test('不同模块和分类分别保存，重新创建会话仓库后仍能读取', () => {
  const saved = storage(), first = createViewMemory(saved)
  first.remember('/jobs/list', 'q=银行&page=2', { top: 240, left: 0 })
  first.remember('/qa/cat/1', 'q=缓存&page=3', { top: 160, left: 0 })
  first.remember('/qa/cat/2', 'q=并发&page=1', { top: 80, left: 0 })
  const reloaded = createViewMemory(saved)
  assert.equal(reloaded.query('/jobs/list'), 'q=银行&page=2')
  assert.equal(reloaded.query('/qa/cat/1'), 'q=缓存&page=3')
  assert.equal(reloaded.query('/qa/cat/2'), 'q=并发&page=1')
  assert.deepEqual(reloaded.position('/qa/cat/1', 'q=缓存&page=3'), { top: 160, left: 0 })
})

test('不同查询分别记录滚动位置，位置读取不会泄露可变引用', () => {
  const memory = createViewMemory()
  memory.remember('/jobs/list', 'page=1&q=银行', { top: 300, left: 20 })
  memory.remember('/jobs/list', 'page=2&q=银行', { top: 200, left: 0 })
  memory.remember('/jobs/list', 'page=3&q=银行')
  assert.deepEqual(memory.position('/jobs/list', 'page=1&q=银行'), { top: 300, left: 20 })
  assert.deepEqual(memory.position('/jobs/list', 'page=3&q=银行'), { top: 0, left: 0 })
  memory.position('/jobs/list', 'page=1&q=银行').top = 999
  assert.equal(memory.position('/jobs/list', 'page=1&q=银行').top, 300)
})

test('浏览器拒绝存储或配额不足时，仍能在当前应用内恢复', () => {
  const memory = createViewMemory({ getItem: () => { throw Error('denied') }, setItem: () => { throw Error('quota') } })
  assert.doesNotThrow(() => memory.remember('/jobs/list', 'page=2', { top: 50, left: 0 }))
  assert.equal(memory.query('/jobs/list'), 'page=2')
  assert.equal(memory.position('/jobs/list', 'page=2').top, 50)
})

test('损坏或旧版本缓存安全降级，非法滚动坐标不恢复', () => {
  for (const raw of ['{oops', 'null', '{"version":0,"pages":[]}']) {
    const memory = createViewMemory({ getItem: () => raw, setItem: () => {} })
    assert.equal(memory.query('/jobs/list'), undefined)
  }
  const raw = JSON.stringify({ version: 1, pages: [
    ['/jobs/list', { query: 'page=1', positions: [['page=1', { top: -2, left: 0 }]] }],
    ['/qa/cat/1', { query: 'page=2', positions: [['page=2', { top: 80, left: 0 }]] }],
    ['broken', null],
  ] })
  const memory = createViewMemory({ getItem: () => raw, setItem: () => {} })
  assert.equal(memory.position('/jobs/list', 'page=1').top, 0)
  assert.equal(memory.position('/qa/cat/1', 'page=2').top, 80)
})

test('会话缓存限制页面数及每个页面的位置数量', () => {
  const saved = storage(), memory = createViewMemory(saved)
  for (let id = 0; id < 81; id++) memory.remember(`/qa/cat/${id}`, 'page=1')
  assert.equal(memory.query('/qa/cat/0'), undefined)
  assert.equal(memory.query('/qa/cat/80'), 'page=1')
  for (let page = 1; page <= 9; page++) memory.remember('/qa/cat/80', `page=${page}`, { top: page * 10, left: 0 })
  assert.equal(memory.position('/qa/cat/80', 'page=1').top, 0)
  assert.equal(createViewMemory(saved).position('/qa/cat/80', 'page=9').top, 90)
})
