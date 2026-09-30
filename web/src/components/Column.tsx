import { useDroppable } from '@dnd-kit/core'
import type { Status, Task } from '../types'
import { TaskCard } from './TaskCard'

const LABEL: Record<Status, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
}

export function Column({
  status,
  tasks,
  onStatusChange,
  onRetry,
  onDelete,
}: {
  status: Status
  tasks: Task[]
  onStatusChange: (id: string, status: Status) => void
  onRetry: (id: string) => void
  onDelete: (id: string) => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status })

  return (
    <div
      ref={setNodeRef}
      className={`flex min-h-[200px] flex-1 flex-col gap-2 rounded-lg border p-3 ${
        isOver ? 'border-slate-600 bg-slate-900/60' : 'border-slate-800 bg-slate-900/30'
      }`}
    >
      <h2 className="flex items-center justify-between text-sm font-semibold text-slate-300">
        {LABEL[status]}
        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
          {tasks.length}
        </span>
      </h2>
      {tasks.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          onStatusChange={(next) => onStatusChange(task.id, next)}
          onRetry={() => onRetry(task.id)}
          onDelete={() => onDelete(task.id)}
        />
      ))}
    </div>
  )
}
