/** 投递状态 key（与后端 constants 一致） */
export type ApplicationStatus =
  | 'applied'
  | 'viewed'
  | 'assessment'
  | 'written_test'
  | 'interviewing'
  | 'offer'
  | 'rejected'
  | 'declined'

/** 流程轮次类型（测评/笔试/面试等） */
export type RoundType =
  | 'assessment'
  | 'written_test'
  | 'first'
  | 'second'
  | 'third'
  | 'hr'
  | 'final'
  | 'other'

/** 轮次结果 */
export type RoundResult = 'pending' | 'passed' | 'failed'

/** 流程轮次 */
export interface InterviewRound {
  id: number
  applicationId: number
  roundType: RoundType
  startAt: string | null
  durationMinutes: number | null
  /** 截止时间 = 开始时间 + 持续时间（后端自动计算） */
  scheduledAt: string | null
  result: RoundResult
  reviewNote: string | null
  createdAt: string
  updatedAt: string
}

/** 状态变化记录（每次状态变更自动追加） */
export interface StatusHistory {
  id: number
  applicationId: number
  status: ApplicationStatus
  changedAt: string
  createdAt: string
  updatedAt: string
}

/** 投递记录（内嵌轮次数组与状态历史） */
export interface Application {
  id: number
  company: string
  position: string | null
  channel: string | null
  url: string | null
  applyDate: string | null
  salary: string | null
  location: string | null
  status: ApplicationStatus
  /** 挂的阶段（rejected 时后端自动推断，如 first = 一面挂） */
  rejectStage: string | null
  note: string | null
  rounds: InterviewRound[]
  statusHistory: StatusHistory[]
  createdAt: string
  updatedAt: string
}

/** 新增/编辑投递表单（applyDate 传 YYYY-MM-DD 字符串） */
export interface ApplicationPayload {
  company: string
  position?: string | null
  channel?: string | null
  url?: string | null
  applyDate?: string | null
  salary?: string | null
  location?: string | null
  status?: ApplicationStatus
  note?: string | null
}

/** 新增/编辑轮次表单（截止时间由后端按 开始+持续 计算，不直接提交） */
export interface RoundPayload {
  roundType: RoundType
  startAt?: string | null
  durationMinutes?: number | null
  result?: RoundResult
  reviewNote?: string | null
}

/** 自定义日程类型 */
export type EventType = 'talk' | 'other'

/** 独立自定义日程（宣讲会等，可不关联投递） */
export interface ScheduleEvent {
  id: number
  title: string
  eventType: EventType
  eventTime: string
  location: string | null
  note: string | null
  applicationId: number | null
  createdAt: string
  updatedAt: string
}

/** 新增/编辑日程表单（eventTime 传 YYYY-MM-DDTHH:mm:ss 字符串） */
export interface EventPayload {
  title: string
  eventType?: EventType
  eventTime?: string | null
  location?: string | null
  note?: string | null
  applicationId?: number | null
}