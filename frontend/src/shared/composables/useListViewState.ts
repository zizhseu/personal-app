import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, watch, type InjectionKey, type Ref, type WatchStopHandle } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { querySignature, resolveView, writeView, type ViewField, type ViewFields, type ViewQuery, type ViewValues } from '../state/pageState'
import { usePageStateStore } from '../state/pageStateStore'

export const pageScrollKey: InjectionKey<Readonly<Ref<HTMLElement | null>>> = Symbol('page-scroll-container')

/** 各列表共享恢复逻辑；数据就绪后再校正页码与恢复实际内容区的位置。 */
export function useListViewState<F extends ViewFields & { page: ViewField<number> }>(fields: F, options: {
  routes: string[]
  ready: () => boolean
  count: () => number
  pageSize: number
}) {
  const route = useRoute(), router = useRouter(), memory = usePageStateStore()
  const container = inject(pageScrollKey, computed(() => null))
  const ownsRoute = () => options.routes.includes(String(route.name))
  let path = route.path
  const state = reactive(resolveView(fields, route.query, memory.query(path))) as ViewValues<F>
  let query = writeView(fields, state), signature = querySignature(query)
  let criteria = criteriaSignature(query), applying = false, disposed = false, leaving = false
  let restoring = true, restoreVersion = 0, frame = 0, scrollTimer: ReturnType<typeof setTimeout> | undefined
  let pendingQuery: ViewQuery | undefined, syncing: Promise<void> | undefined, inFlight = ''
  let stopResults: WatchStopHandle | undefined

  function criteriaSignature(value: ViewQuery) {
    const { page: _page, ...rest } = value
    return querySignature(rest)
  }
  function capture() {
    if (restoring || !container.value) { memory.remember(path, signature); return }
    memory.remember(path, signature, { top: container.value.scrollTop, left: container.value.scrollLeft })
  }
  function stopRestore() { restoreVersion++; cancelAnimationFrame(frame); restoring = false }
  function syncUrl() {
    pendingQuery = query
    if (syncing) return syncing
    syncing = (async () => {
      while (pendingQuery && !disposed && !leaving && ownsRoute() && route.path === path) {
        const next = pendingQuery
        pendingQuery = undefined
        if (querySignature(next) === querySignature(Object.fromEntries(Object.keys(fields).map(key => [key, route.query[key]])))) continue
        const extra = Object.fromEntries(Object.entries(route.query).filter(([key]) => !Object.hasOwn(fields, key)))
        inFlight = querySignature(next)
        try { await router.replace({ path, query: { ...extra, ...next }, hash: route.hash }) }
        finally { inFlight = '' }
      }
    })().finally(() => {
      syncing = undefined
      if (pendingQuery && !disposed && !leaving && ownsRoute()) void syncUrl()
    })
    return syncing
  }

  function readRoute() {
    if (!ownsRoute()) return
    const incoming = querySignature(writeView(fields, resolveView(fields, route.query, memory.query(route.path))))
    if (path === route.path && inFlight && incoming === inFlight) return
    stopRestore()
    pendingQuery = undefined
    path = route.path
    applying = true
    Object.assign(state, resolveView(fields, route.query, memory.query(path)))
    applying = false
    query = writeView(fields, state)
    signature = querySignature(query)
    criteria = criteriaSignature(query)
    leaving = false
    restoring = true
    memory.remember(path, signature)
    void syncUrl()
    void restoreScroll()
  }

  watch(state, () => {
    if (applying || leaving || !ownsRoute() || route.path !== path) return
    const nextCriteria = criteriaSignature(writeView(fields, state))
    if (nextCriteria !== criteria) {
      applying = true
      state.page = 1 as ViewValues<F>['page']
      applying = false
    }
    query = writeView(fields, state)
    const nextSignature = querySignature(query)
    if (nextSignature === signature) return
    stopRestore()
    signature = nextSignature
    criteria = nextCriteria
    memory.remember(path, signature, { top: 0, left: 0 })
    container.value?.scrollTo({ top: 0, left: 0 })
    void syncUrl()
  }, { deep: true, flush: 'sync' })
  watch(() => route.fullPath, readRoute, { flush: 'sync' })

  async function restoreScroll() {
    if (!restoring || leaving || !options.ready() || !ownsRoute()) return
    const version = ++restoreVersion
    await nextTick()
    frame = requestAnimationFrame(() => {
      if (version !== restoreVersion || disposed || leaving || !ownsRoute()) return
      const position = memory.position(path, signature)
      container.value?.scrollTo({ top: position.top, left: position.left })
      restoring = false
      capture()
    })
  }
  function onScroll() {
    if (restoring || leaving) return
    clearTimeout(scrollTimer)
    scrollTimer = setTimeout(capture, 120)
  }
  function onUserScroll() { if (restoring) stopRestore() }
  const onPageHide = () => capture()
  onBeforeRouteLeave(() => { capture(); leaving = true; pendingQuery = undefined; stopRestore() })
  onBeforeRouteUpdate(to => {
    if (to.path !== path || querySignature(to.query) !== querySignature(route.query) && !inFlight) {
      capture(); stopRestore()
    }
  })
  onMounted(async () => {
    await nextTick()
    if (disposed) return
    container.value?.addEventListener('scroll', onScroll, { passive: true })
    container.value?.addEventListener('wheel', onUserScroll, { passive: true })
    container.value?.addEventListener('touchstart', onUserScroll, { passive: true })
    window.addEventListener('pagehide', onPageHide)
    // 此处才读取列表总数，避免组件初始化及首次数据加载前将恢复页码改成 1。
    stopResults = watch(() => [options.ready(), options.count(), state.page] as const, ([ready, count, page]) => {
      if (!ready || leaving || !ownsRoute()) return
      const maximum = Math.max(1, Math.ceil(count / options.pageSize))
      if (typeof page === 'number' && page > maximum) state.page = maximum as ViewValues<F>['page']
      void restoreScroll()
    }, { immediate: true, flush: 'post' })
    memory.remember(path, signature)
    void syncUrl()
  })
  onBeforeUnmount(() => {
    if (!leaving && ownsRoute()) capture()
    disposed = true
    stopResults?.()
    stopRestore()
    clearTimeout(scrollTimer)
    container.value?.removeEventListener('scroll', onScroll)
    container.value?.removeEventListener('wheel', onUserScroll)
    container.value?.removeEventListener('touchstart', onUserScroll)
    window.removeEventListener('pagehide', onPageHide)
  })

  async function navigate(target: RouteLocationRaw) {
    const origin = path
    // 先完成当前历史项的条件更新，再打开详情，避免最后一次输入被导航取消。
    void syncUrl()
    while (syncing && !disposed && !leaving) await syncing
    if (!disposed && !leaving && ownsRoute() && route.path === origin) await router.push(target)
  }
  function reset() {
    Object.assign(state, resolveView(fields, {}))
    stopRestore()
    memory.remember(path, signature, { top: 0, left: 0 })
    container.value?.scrollTo({ top: 0, left: 0 })
  }
  return { state, navigate, reset }
}
