import { DndContext, type DragEndEvent } from '@dnd-kit/core'
import type { Status, Task } from '../types'
import { Column } from './Column'

const STATUSES: Status[] = ['pending', 'in_progress', 'completed']

export function Board({
  tasks,
  onStatusChange,
  onRetry,
}: {
  tasks: Task[]
  onStatusChange: (id: string, status: Status) => void
  onRetry: (id: string) => void
}) {
  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over) return
    const status = over.id as Status
    const task = tasks.find((t) => t.id === active.id)
    if (task && task.status !== status) onStatusChange(task.id, status)
  }

  return (
    <DndContext onDragEnd={handleDragEnd}>
      <div className="flex flex-col gap-3 sm:flex-row">
        {STATUSES.map((status) => (
          <Column
            key={status}
            status={status}
            tasks={tasks.filter((t) => t.status === status)}
            onStatusChange={onStatusChange}
            onRetry={onRetry}
          />
        ))}
      </div>
    </DndContext>
  )
}
