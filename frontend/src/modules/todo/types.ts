export interface TodoCategory {
  id: number
  name: string
}

export interface TodoItem {
  id: number
  categoryId: number
  title: string
  note: string | null
  dueAt: string | null
  completed: boolean
  completedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface TodoPayload {
  categoryId: number
  title: string
  note: string | null
  dueAt: string | null
}

export type TodoUpdate = Partial<Omit<TodoPayload, 'categoryId'> & { completed: boolean }>
