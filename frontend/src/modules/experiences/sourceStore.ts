import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchSources, selectSource } from './api'
import type { SourcePlatform } from './types'

export const useSourceStore = defineStore('experience-sources', () => {
  const platforms = ref<SourcePlatform[]>([]), loaded = ref(false), failed = ref(false)
  let pending: Promise<void> | null = null
  function load(force = false): Promise<void> {
    if (pending) return pending
    if (loaded.value && !force) return Promise.resolve()
    pending = (async () => {
      try { platforms.value = (await fetchSources()).platforms; loaded.value = true; failed.value = false }
      catch { failed.value = true }
      finally { pending = null }
    })()
    return pending
  }
  function active(platform: string) {
    const source = platforms.value.find(value => value.id === platform)
    return source?.providers.find(value => value.id === source.activeProvider)
  }
  async function select(platform: string, providerId: string) {
    platforms.value = (await selectSource(platform, providerId)).platforms
  }
  return { platforms, loaded, failed, load, active, select }
})
