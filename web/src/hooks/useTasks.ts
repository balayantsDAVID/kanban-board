import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Status, Task } from '../types'

export interface TaskEvent {
  type: 'task.created' | 'task.updated' | 'task.deleted'
  task: Task
}

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(async () => {
    setTasks(await api.tasks())
  }, [])

  useEffect(() => {
    void refetch().finally(() => setLoading(false))
  }, [refetch])

  const updateStatus = useCallback(async (id: string, status: Status) => {
    let previous: Task[] = []
    setTasks((current) => {
      previous = current
      return current.map((t) => (t.id === id ? { ...t, status } : t))
    })
    try {
      await api.updateTask(id, { status })
    } catch (err) {
      setTasks(previous)
      throw err
    }
  }, [])

  const retry = useCallback(async (id: string) => {
    const task = await api.retryTask(id)
    setTasks((current) => current.map((t) => (t.id === id ? task : t)))
  }, [])

  const applyEvent = useCallback((event: TaskEvent) => {
    setTasks((current) => {
      if (event.type === 'task.deleted') {
        return current.filter((t) => t.id !== event.task.id)
      }
      const exists = current.some((t) => t.id === event.task.id)
      if (exists) {
        return current.map((t) => (t.id === event.task.id ? event.task : t))
      }
      return [event.task, ...current]
    })
  }, [])

  return { tasks, loading, refetch, updateStatus, retry, applyEvent }
}
