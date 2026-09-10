import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import type {
  Application,
  ApplicationStatus,
  ApplicationPayload,
  EventPayload,
  RoundPayload,
  ScheduleEvent,
} from './types'
import * as api from './api'

/** 全量数据 + 增删改后统一刷新，保证四个页面共用一致数据源 */
export const useJobsStore = defineStore('jobs', {
  state: () => ({
    applications: [] as Application[],
    events: [] as ScheduleEvent[],
    loaded: false,
    loading: false,
  }),
  actions: {
    async loadAll() {
      this.loading = true
      try {
        const [applications, events] = await Promise.all([
          api.fetchApplications(),
          api.fetchEvents(),
        ])
        this.applications = applications
        this.events = events
        this.loaded = true
      } finally {
        this.loading = false
      }
    },
    /** 确保数据已加载（刷新详情页 URL 直开时兜底） */
    async ensureLoaded() {
      if (!this.loaded) await this.loadAll()
    },
    async create(payload: ApplicationPayload) {
      await api.createApplication(payload)
      ElMessage.success('新增投递成功')
      await this.loadAll()
    },
    async update(id: number, payload: Partial<ApplicationPayload>) {
      await api.updateApplication(id, payload)
      ElMessage.success('保存成功')
      await this.loadAll()
    },
    async quickSetStatus(id: number, status: ApplicationStatus) {
      await api.patchStatus(id, status)
      ElMessage.success('状态已更新')
      await this.loadAll()
    },
    async remove(id: number) {
      await api.deleteApplication(id)
      ElMessage.success('已删除')
      await this.loadAll()
    },
    async addRound(applicationId: number, payload: RoundPayload) {
      await api.createRound(applicationId, payload)
      ElMessage.success('已添加轮次')
      await this.loadAll()
    },
    async updateRound(roundId: number, payload: Partial<RoundPayload>) {
      await api.updateRound(roundId, payload)
      ElMessage.success('保存成功')
      await this.loadAll()
    },
    async removeRound(roundId: number) {
      await api.deleteRound(roundId)
      ElMessage.success('已删除轮次')
      await this.loadAll()
    },
    async addEvent(payload: EventPayload) {
      await api.createEvent(payload)
      ElMessage.success('已添加日程')
      await this.loadAll()
    },
    async updateEvent(id: number, payload: Partial<EventPayload>) {
      await api.updateEvent(id, payload)
      ElMessage.success('保存成功')
      await this.loadAll()
    },
    async removeEvent(id: number) {
      await api.deleteEvent(id)
      ElMessage.success('已删除日程')
      await this.loadAll()
    },
  },
})