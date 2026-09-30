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
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    try {
      setTasks(await api.tasks())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks')
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .tasks()
      .then((list) => !cancelled && setTasks(list))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : 'Failed to load tasks'))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

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
      setError(err instanceof Error ? err.message : 'Failed to update task')
    }
  }, [])

  const createTask = useCallback(async (title: string) => {
    try {
      const task = await api.createTask(title)
      setTasks((current) => [task, ...current])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create task')
    }
  }, [])

  const deleteTask = useCallback(async (id: string) => {
    let previous: Task[] = []
    setTasks((current) => {
      previous = current
      return current.filter((t) => t.id !== id)
    })
    try {
      await api.deleteTask(id)
    } catch (err) {
      setTasks(previous)
      setError(err instanceof Error ? err.message : 'Failed to delete task')
    }
  }, [])

  const retry = useCallback(async (id: string) => {
    try {
      const task = await api.retryTask(id)
      setTasks((current) => current.map((t) => (t.id === id ? task : t)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed')
    }
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

  return {
    tasks,
    loading,
    error,
    clearError: () => setError(null),
    refetch,
    updateStatus,
    createTask,
    deleteTask,
    retry,
    applyEvent,
  }
}
