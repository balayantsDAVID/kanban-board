import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import type { Task } from '../types'
import { useTasks } from './useTasks'

vi.mock('../api', () => ({
  api: {
    tasks: vi.fn(),
    updateTask: vi.fn(),
    createTask: vi.fn(),
    deleteTask: vi.fn(),
    retryTask: vi.fn(),
  },
}))

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: '1',
    title: 'task',
    description: null,
    tags: [],
    status: 'pending',
    priority: 'normal',
    due_at: null,
    source: 'web',
    raw_text: null,
    language: null,
    transcription_status: 'none',
    transcription_error: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

beforeEach(() => {
  vi.mocked(api.tasks).mockResolvedValue([])
})

describe('applyEvent', () => {
  it('adds a new task on task.created', async () => {
    const { result } = renderHook(() => useTasks())
    await waitFor(() => expect(result.current.loading).toBe(false))

    const task = makeTask()
    act(() => result.current.applyEvent({ type: 'task.created', task }))

    expect(result.current.tasks).toEqual([task])
  })

  it('replaces an existing task on task.updated', async () => {
    const task = makeTask()
    vi.mocked(api.tasks).mockResolvedValue([task])
    const { result } = renderHook(() => useTasks())
    await waitFor(() => expect(result.current.tasks).toEqual([task]))

    const updated = { ...task, status: 'completed' as const }
    act(() => result.current.applyEvent({ type: 'task.updated', task: updated }))

    expect(result.current.tasks).toEqual([updated])
  })

  it('removes a task on task.deleted', async () => {
    const task = makeTask()
    vi.mocked(api.tasks).mockResolvedValue([task])
    const { result } = renderHook(() => useTasks())
    await waitFor(() => expect(result.current.tasks).toEqual([task]))

    act(() => result.current.applyEvent({ type: 'task.deleted', task }))

    expect(result.current.tasks).toEqual([])
  })
})

describe('updateStatus', () => {
  it('rolls back the optimistic update when the API call fails', async () => {
    const task = makeTask()
    vi.mocked(api.tasks).mockResolvedValue([task])
    vi.mocked(api.updateTask).mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useTasks())
    await waitFor(() => expect(result.current.tasks).toEqual([task]))

    await act(async () => {
      await result.current.updateStatus(task.id, 'completed')
    })

    expect(result.current.tasks).toEqual([task])
    expect(result.current.error).toBe('boom')
  })
})
