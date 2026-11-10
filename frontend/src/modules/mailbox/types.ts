import type { InterviewRound, RoundResult, RoundType } from '@/modules/jobs/types'

export interface MailAccount {
  id: number
  address: string
  enabled: boolean
  baselineAt: string
  lastScanAt: string | null
  nextScanAt: string | null
  scanning: boolean
  lastError: string | null
}

export interface MailSettings {
  account: MailAccount | null
  intervalMinutes: number
  authorizationConfigured: boolean
}

export interface MailDraft {
  address: string
  authorizationCode?: string
  enabled: boolean
}

export interface MailProposal {
  category: string
  eventType: string | null
  company: string | null
  matchedCompany?: string | null
  companyMatchType?: 'exact' | 'alias' | 'unit' | 'uncertain'
  companyMatchReason?: string | null
  targetPosition?: string | null
  positionAction?: 'existing' | 'create' | 'uncertain'
  positionMatchReason?: string | null
  companySearchKeywords?: string[]
  companySearchResults?: { keyword: string; companies: string[]; hasMore: boolean }[]
  position: string | null
  roundType: RoundType | null
  result: RoundResult | null
  startAt: string | null
  deadlineAt: string | null
  evidence: string
  reason: string
}

export interface MailMessage {
  id: number
  subject: string
  sender: string
  sentAt: string | null
  receivedAt: string
  status: string
  reason: string | null
  body?: string
  proposal: MailProposal | null
  applicationId: number | null
  roundId: number | null
  duplicateOf: number | null
  attachments: string[]
  changes: {
    before: { status: string; round?: InterviewRound | null }
    after: { status: string; round?: InterviewRound }
    createdPosition?: { position: string; positionVersion: number } | null
  } | null
  changeSummary?: string | null
}

export interface MailCompanyTarget {
  applicationId: number
  company: string
  currentPosition: string | null
  expectedUpdatedAt: string
  expectedPositionVersion: number
  expectedCompanySnapshot: string
}

export interface MailTarget {
  applicationId: number
  company: string
  position: string | null
  positionVersion: number
  displayOrder: number
  status: string
  expectedUpdatedAt: string
  expectedSnapshot: string
  rounds: InterviewRound[]
}

export interface MessageList {
  items: MailMessage[]
  total: number
  counts: Record<string, number>
}
