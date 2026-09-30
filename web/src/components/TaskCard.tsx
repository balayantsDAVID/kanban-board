import { useDraggable } from '@dnd-kit/core'
import { useState } from 'react'
import type { Status, Task } from '../types'

const PRIORITY_STYLE: Record<Task['priority'], string> = {
  low: 'bg-slate-800 text-slate-400',
  normal: 'bg-slate-800 text-slate-300',
  high: 'bg-amber-900/60 text-amber-300',
  urgent: 'bg-red-900/60 text-red-300',
}

const SOURCE_ICON: Record<Task['source'], string> = {
  text: '💬',
  voice: '🎤',
  web: '🖥️',
}

const STATUS_ORDER: Status[] = ['pending', 'in_progress', 'completed']
const STATUS_LABEL: Record<Status, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
}

function formatDue(dueAt: string | null): string | null {
  if (!dueAt) return null
  return new Date(dueAt).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function TaskCard({
  task,
  onStatusChange,
  onRetry,
  onDelete,
}: {
  task: Task
  onStatusChange: (status: Status) => void
  onRetry: () => void
  onDelete: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
  })
  const [showTranscript, setShowTranscript] = useState(false)
  const due = formatDue(task.due_at)
  const nextStatus = STATUS_ORDER[(STATUS_ORDER.indexOf(task.status) + 1) % STATUS_ORDER.length]

  return (
    <div
      ref={setNodeRef}
      style={
        transform
          ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 10 }
          : undefined
      }
      className={`rounded-md border border-slate-800 bg-slate-900 p-3 shadow-sm ${
        isDragging ? 'opacity-50' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <button
          {...listeners}
          {...attributes}
          className="cursor-grab text-left text-sm font-medium text-slate-100 active:cursor-grabbing"
        >
          <span className="mr-1">{SOURCE_ICON[task.source]}</span>
          {task.title}
        </button>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase ${PRIORITY_STYLE[task.priority]}`}>
          {task.priority}
        </span>
        <button
          onClick={() => {
            if (window.confirm('Delete this task?')) onDelete()
          }}
          className="shrink-0 text-slate-600 hover:text-red-400"
          aria-label="Delete task"
        >
          ✕
        </button>
      </div>

      {task.tags.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {task.tags.map((tag) => (
            <span key={tag} className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
              #{tag}
            </span>
          ))}
        </div>
      )}

      {due && <p className="mt-1 text-xs text-slate-500">due {due}</p>}

      {task.transcription_status === 'processing' && (
        <p className="mt-1 text-xs text-slate-500">🎤 Recognizing…</p>
      )}

      {task.transcription_status === 'done' && task.raw_text && (
        <div className="mt-1">
          <button
            onClick={() => setShowTranscript((v) => !v)}
            className="text-xs text-slate-500 underline hover:text-slate-300"
          >
            {showTranscript ? 'hide transcript' : 'show transcript'}
          </button>
          {showTranscript && <p className="mt-1 text-xs text-slate-400">{task.raw_text}</p>}
        </div>
      )}

      {task.transcription_status === 'failed' && (
        <div className="mt-1 flex items-center justify-between">
          <span className="text-xs text-red-400">❌ Recognition failed</span>
          <button
            onClick={onRetry}
            className="rounded bg-red-900/60 px-2 py-0.5 text-xs text-red-200 hover:bg-red-900"
          >
            Retry
          </button>
        </div>
      )}

      <button
        onClick={() => onStatusChange(nextStatus)}
        className="mt-2 w-full rounded bg-slate-800 py-1 text-xs text-slate-400 hover:bg-slate-700 sm:hidden"
      >
        Move to {STATUS_LABEL[nextStatus]}
      </button>
    </div>
  )
}
