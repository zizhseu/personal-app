/** 投递状态 key（与后端 constants 一致） */
export type ApplicationStatus =
  | 'screening'
  | 'assessment'
  | 'written_test'
  | 'interviewing'
  | 'offer'

/** 流程轮次类型（测评/笔试/面试等） */
export type RoundType =
  | 'assessment'
  | 'written_test'
  | 'ai'
  | 'first'
  | 'second'
  | 'third'
  | 'hr'
  | 'final'
  | 'other'

/** 轮次结果（accepted / rejected_offer 仅状态为 Offer 时使用） */
export type RoundResult =
  | 'not_started'
  | 'completed'
  | 'not_attended'
  | 'passed'
  | 'failed'
  | 'accepted'
  | 'rejected_offer'

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
  /** 结果最后一次被修改的时间（= 实际完成时间） */
  resultChangedAt: string | null
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
  url: string | null
  applyDate: string | null
  salary: string | null
  /** 意向 Base 城市（多选） */
  base: string[] | null
  status: ApplicationStatus
  /** Offer 决定（accepted / rejected_offer），仅状态为 Offer 时有意义 */
  offerDecision: 'accepted' | 'rejected_offer' | null
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
  url?: string | null
  applyDate?: string | null
  salary?: string | null
  base?: string[] | null
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

/** 日程条目（日程页内部结构：轮次与自定义日程归一后） */
export interface ScheduleItem {
  key: string
  kind: 'round' | 'event'
  /** 展示/排序时间（轮次=截止时间，日程=开始时间） */
  scheduledAt: string
  /** 已完成的轮次：实际完成时间（= 结果最后一次修改时间），无则为 null */
  doneAt: string | null
  /** MM-DD HH:mm */
  time: string
  typeLabel: string
  title: string
  location: string | null
  round?: InterviewRound
  event?: ScheduleEvent
  applicationId?: number | null
}