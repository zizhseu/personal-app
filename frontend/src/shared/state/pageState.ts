/** 列表视图的序列化与会话存储；只保存查询条件和位置，不保存业务记录。 */
export type QueryValue = string | null | (string | null)[] | undefined
export type ViewQuery = Record<string, QueryValue>
export type ViewValue = string | number | string[]
export interface ViewField<T extends ViewValue = ViewValue> { initial: T; read: (value: unknown) => T }
export type ViewFields = Record<string, ViewField>
export type ViewValues<F extends ViewFields> = { [K in keyof F]: ReturnType<F[K]['read']> }
export interface ScrollPosition { top: number; left: number }
interface StorageLike { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void }
interface SavedView { query: string; positions: [string, ScrollPosition][] }

const first = (value: unknown) => Array.isArray(value) ? value[0] : value
export const textField = (max = 500): ViewField<string> => ({
  initial: '', read: value => typeof first(value) === 'string' ? String(first(value)).slice(0, max) : '',
})
export const choiceField = <T extends string>(initial: T, choices: readonly T[]): ViewField<T> => ({
  initial, read: value => choices.includes(first(value) as T) ? first(value) as T : initial,
})
export const listField = <T extends string = string>(choices?: readonly T[]): ViewField<T[]> => ({
  initial: [], read: value => [...new Set((Array.isArray(value) ? value : [value])
    .filter((item): item is T => typeof item === 'string' && item.length > 0 && item.length <= 100
      && (!choices || choices.includes(item as T))))].slice(0, 50).sort(),
})
export const pageField = (): ViewField<number> => ({
  initial: 1, read: value => {
    const raw = first(value), number = typeof raw === 'number' || typeof raw === 'string' ? Number(raw) : NaN
    return Number.isSafeInteger(number) && number >= 1 && number <= 100_000 ? number : 1
  },
})

export function readView<F extends ViewFields>(fields: F, query: Record<string, unknown>): ViewValues<F> {
  return Object.fromEntries(Object.entries(fields).map(([key, field]) => [key, field.read(query[key])])) as ViewValues<F>
}

export function writeView<F extends ViewFields>(fields: F, values: ViewValues<F>): ViewQuery {
  const query: ViewQuery = {}
  for (const [key, field] of Object.entries(fields)) {
    const value = field.read(values[key])
    // page=1 也写入地址，明确表示默认视图，避免返回时复活旧筛选。
    if (key !== 'page' && JSON.stringify(value) === JSON.stringify(field.initial)) continue
    query[key] = typeof value === 'number' ? String(value) : value
  }
  return query
}

export function querySignature(query: ViewQuery): string {
  const params = new URLSearchParams()
  Object.keys(query).sort().forEach(key => {
    const value = query[key]
    for (const item of Array.isArray(value) ? value : [value]) if (typeof item === 'string') params.append(key, item)
  })
  return params.toString()
}

export function parseSignature(signature: string): ViewQuery {
  const params = new URLSearchParams(signature), query: ViewQuery = {}
  for (const key of new Set(params.keys())) {
    const values = params.getAll(key)
    Object.defineProperty(query, key, { value: values.length === 1 ? values[0] : values, enumerable: true })
  }
  return query
}

export function resolveView<F extends ViewFields>(fields: F, query: ViewQuery, saved?: string): ViewValues<F> {
  const explicit = Object.keys(fields).some(key => Object.hasOwn(query, key))
  return readView(fields, explicit || !saved ? query : parseSignature(saved))
}

const storageKey = 'personal-app.page-views.v1'
const validPosition = (value: unknown): value is ScrollPosition => !!value && typeof value === 'object'
  && ['top', 'left'].every(key => {
    const number = (value as Record<string, unknown>)[key]
    return typeof number === 'number' && Number.isFinite(number) && number >= 0 && number <= 10_000_000
  })

export function createViewMemory(storage?: StorageLike) {
  const pages = new Map<string, SavedView>()
  try {
    const raw = storage?.getItem(storageKey)
    const saved = raw && raw.length < 500_000 ? JSON.parse(raw) : null
    if (saved?.version === 1 && Array.isArray(saved.pages)) {
      for (const entry of saved.pages.slice(-80)) {
        if (!Array.isArray(entry) || entry.length !== 2) continue
        const [path, view] = entry
        if (typeof path !== 'string' || !path.startsWith('/') || path.length > 300
          || !view || typeof view.query !== 'string' || view.query.length > 16_000 || !Array.isArray(view.positions)) continue
        const positions: SavedView['positions'] = view.positions.filter((item: unknown) => Array.isArray(item)
          && typeof item[0] === 'string' && item[0].length <= 16_000 && validPosition(item[1])).slice(-8)
        pages.set(path, { query: view.query, positions })
      }
    }
  } catch { /* 会话存储损坏或被禁用时继续使用内存。 */ }

  function save() {
    try { storage?.setItem(storageKey, JSON.stringify({ version: 1, pages: [...pages] })) }
    catch { /* 存储配额不足不影响搜索与导航。 */ }
  }
  function remember(path: string, query: string, position?: ScrollPosition) {
    const view = pages.get(path) ?? { query, positions: [] }
    view.query = query
    if (position && validPosition(position)) {
      view.positions = [...view.positions.filter(([key]) => key !== query), [query, { ...position }] as [string, ScrollPosition]].slice(-8)
    }
    pages.delete(path)
    pages.set(path, view)
    if (pages.size > 80) pages.delete(pages.keys().next().value!)
    save()
  }
  return {
    remember,
    query: (path: string) => pages.get(path)?.query,
    position: (path: string, query: string): ScrollPosition => ({
      ...(pages.get(path)?.positions.find(([key]) => key === query)?.[1] ?? { top: 0, left: 0 }),
    }),
  }
}
