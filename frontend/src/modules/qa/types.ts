/** 面试八股分类（用户可增删改的实体） */
export interface QaCategoryEntity {
  id: number
  name: string
  createdAt: string
  updatedAt: string
}

/** 掌握状态 */
export type QaStatus = 'learning' | 'mastered'

/** 面试八股问答 */
export interface QaItem {
  id: number
  categoryId: number
  categoryName: string | null
  question: string
  answer: string | null
  /** 自定义标签（多选） */
  tags: string[] | null
  status: QaStatus
  /** 最后阅读时间（进入详情页时更新） */
  lastReadAt: string | null
  createdAt: string
  updatedAt: string
}

/** 新增/编辑表单 */
export interface QaPayload {
  categoryId: number
  question: string
  answer?: string | null
  tags?: string[] | null
}