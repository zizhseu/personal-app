/** AI 面试对话消息 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** AI 面试对话响应 */
export interface InterviewChatResponse {
  reply: string
}