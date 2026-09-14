import { defineStore } from 'pinia'
import type { AppSettings } from './types'

const STORAGE_KEY = 'app-settings'

const DEFAULTS: AppSettings = {
  importFilenameAsTag: true,
}

function load(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS }
  } catch {
    return { ...DEFAULTS }
  }
}

/** 全局设置：写入即持久化到 localStorage */
export const useSettingsStore = defineStore('settings', {
  state: () => load(),
  actions: {
    update(patch: Partial<AppSettings>) {
      Object.assign(this, patch)
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ ...DEFAULTS, ...(this.$state as AppSettings) }),
      )
    },
  },
})