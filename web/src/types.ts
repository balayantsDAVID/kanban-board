export type Status = 'pending' | 'in_progress' | 'completed'
export type Priority = 'low' | 'normal' | 'high' | 'urgent'
export type Source = 'text' | 'voice' | 'web'
export type TranscriptionStatus = 'none' | 'queued' | 'processing' | 'done' | 'failed'

export interface Task {
  id: string
  title: string
  description: string | null
  tags: string[]
  status: Status
  priority: Priority
  due_at: string | null
  source: Source
  raw_text: string | null
  language: string | null
  transcription_status: TranscriptionStatus
  transcription_error: string | null
  created_at: string
  updated_at: string
}

export interface User {
  id: string
  username: string | null
  first_name: string | null
}
