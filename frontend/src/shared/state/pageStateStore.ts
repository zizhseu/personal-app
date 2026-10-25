import { defineStore } from 'pinia'
import { createViewMemory } from './pageState'

export const usePageStateStore = defineStore('page-views', () => {
  let storage: Storage | undefined
  try { storage = window.sessionStorage } catch { /* 禁止浏览器存储时保留应用内记忆。 */ }
  return createViewMemory(storage)
})
