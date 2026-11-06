import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import type {
  Application,
  ApplicationStatus,
  ApplicationPayload,
  ApplicationUpdatePayload,
  EventPayload,
  RoundPayload,
  RoundCreatePayload,
  PositionDeletePayload,
  PrimaryPositionPayload,
  PositionStatusPayload,
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
    savingPrimaryIds: [] as number[],
    savingPositionStatusKeys: [] as string[],
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
    /** silent = 不弹成功提示（列表内快捷编辑用） */
    async update(id: number, payload: ApplicationUpdatePayload, silent = false) {
      await api.updateApplication(id, payload)
      if (!silent) ElMessage.success('保存成功')
      await this.loadAll()
    },
    async quickSetStatus(id: number, status: ApplicationStatus) {
      await api.patchStatus(id, status)
      ElMessage.success('状态已更新')
      await this.loadAll()
    },
    async setPositionStatus(id: number, payload: PositionStatusPayload) {
      const key = JSON.stringify([id, payload.positionVersion, payload.position])
      if (this.savingPositionStatusKeys.includes(key)) return
      this.savingPositionStatusKeys.push(key)
      try {
        await api.patchPositionStatus(id, payload)
        await this.loadAll()
        ElMessage.success('该岗位状态已更新')
      } finally {
        this.savingPositionStatusKeys = this.savingPositionStatusKeys.filter(value => value !== key)
      }
    },
    async setOfferDecision(id: number, decision: 'accepted' | 'rejected_offer') {
      await api.patchOfferDecision(id, decision)
      ElMessage.success('结果已更新')
      await this.loadAll()
    },
    async remove(id: number) {
      await api.deleteApplication(id)
      ElMessage.success('已删除')
      await this.loadAll()
    },
    async removePosition(id: number, payload: PositionDeletePayload) {
      await api.deletePosition(id, payload)
      ElMessage.success('已删除岗位，公司记录已保留')
      await this.loadAll()
    },
    async setPrimaryPosition(id: number, payload: PrimaryPositionPayload) {
      if (this.savingPrimaryIds.includes(id)) return
      this.savingPrimaryIds.push(id)
      try {
        await api.setPrimaryPosition(id, payload)
        await this.loadAll()
        ElMessage.success('主要岗位已更新，列表将展示该岗位')
      } finally {
        this.savingPrimaryIds = this.savingPrimaryIds.filter(value => value !== id)
      }
    },
    async addRound(applicationId: number, payload: RoundCreatePayload) {
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
    /** 手动删除一条状态变化记录（详情页目录） */
    async removeStatusHistory(historyId: number) {
      await api.deleteStatusHistory(historyId)
      ElMessage.success('已删除该条状态记录')
      await this.loadAll()
    },
    /** 手动删除一条结果变化记录 */
    async removeResultHistory(historyId: number) {
      await api.deleteResultHistory(historyId)
      ElMessage.success('已删除该条结果记录')
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
