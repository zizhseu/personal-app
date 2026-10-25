export interface ResumeSummary { id: number; name: string; updatedAt: string }
export interface ResumeDocument extends ResumeSummary { content: string }
export interface ResumeInput { name: string; content: string }

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  operationId: string
  createdAt: string
}

export interface InterviewSummary {
  id: number
  resumeId: number | null
  resumeName: string
  targetRole: string
  focus: string
  status: 'active' | 'completed'
  createdAt: string
  updatedAt: string
}

export interface InterviewOperation {
  id: string
  kind: 'start' | 'reply' | 'review'
  status: 'pending' | 'failed' | 'succeeded'
  error: string | null
}

export interface ReviewItem {
  questionMessageId: number
  answerMessageId: number
  resumeQuote: string
  assessment: 'solid' | 'partial' | 'needs_work'
  feedback: string
  improvementGuide: string
  knowledgePoints: string[]
}

export interface InterviewReport {
  summary: string
  strengths: string[]
  improvements: string[]
  items: ReviewItem[]
}

export interface ReviewAction { itemIndex: number; kind: 'qa' | 'todo'; targetId: number | null }
export interface InterviewSession extends InterviewSummary {
  resumeContent: string
  messages: ChatMessage[]
  lastOperation: InterviewOperation | null
  report: InterviewReport | null
  actions: ReviewAction[]
}

export interface ReviewActionInput {
  itemIndex: number
  kind: 'qa' | 'todo'
  categoryId: number
  title: string
  content: string
  dueAt?: string | null
}
