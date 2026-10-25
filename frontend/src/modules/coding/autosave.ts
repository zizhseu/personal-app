/** 停止输入后保存；同一时间只发送一个请求，离开页面时可等待最新内容写入。 */
export function createAutosave<T>(options: {
  read: () => T
  dirty: () => boolean
  valid: () => boolean
  write: (snapshot: T) => Promise<void>
  saving: (value: boolean) => void
  failed: (error: unknown, snapshot: T) => number | null
  delay?: number
}) {
  let timer: ReturnType<typeof setTimeout> | undefined
  let pending: Promise<boolean> | null = null
  let disposed = false

  function cancel() {
    if (timer !== undefined) clearTimeout(timer)
    timer = undefined
  }
  function schedule(delay = options.delay ?? 1000) {
    cancel()
    if (disposed || !options.dirty() || !options.valid()) return
    timer = setTimeout(() => { timer = undefined; void run() }, delay)
  }
  function run(): Promise<boolean> {
    if (pending) return pending
    if (disposed || !options.dirty()) return Promise.resolve(true)
    if (!options.valid()) return Promise.resolve(false)
    const snapshot = options.read()
    // 延至微任务执行，确保同步异常也能正确清理 pending。
    pending = Promise.resolve().then(async () => {
      options.saving(true)
      let ok = true
      let retryDelay: number | null = null
      try { await options.write(snapshot) }
      catch (error) {
        ok = false
        cancel()
        if (!disposed) retryDelay = options.failed(error, snapshot)
      }
      finally { pending = null; if (!disposed) options.saving(false) }
      if (!disposed && options.dirty() && options.valid() && timer === undefined) {
        if (ok) schedule(0)
        else if (retryDelay !== null) schedule(retryDelay)
      }
      return ok
    })
    return pending
  }
  async function flush(): Promise<boolean> {
    cancel()
    // 即使保存中又输入，也继续写入最新快照，不并发提交或丢掉后来的修改。
    while (!disposed && (pending || options.dirty())) {
      if (!await run()) return false
      cancel()
    }
    return !options.dirty()
  }
  function dispose() { disposed = true; cancel() }
  return { schedule, flush, cancel, dispose, wait: () => pending ?? Promise.resolve(true) }
}
