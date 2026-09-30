import { useEffect, useRef, useState } from 'react'
import { notifyAuthExpired } from '../api'
import type { TaskEvent } from './useTasks'

const BACKOFF_SEC = [1, 2, 5, 10]

export type ConnectionState = 'connected' | 'reconnecting'

export function useEventStream(onEvent: (event: TaskEvent) => void, onReconnect: () => void) {
  const [state, setState] = useState<ConnectionState>('connected')
  const onEventRef = useRef(onEvent)
  const onReconnectRef = useRef(onReconnect)

  useEffect(() => {
    onEventRef.current = onEvent
    onReconnectRef.current = onReconnect
  }, [onEvent, onReconnect])

  useEffect(() => {
    let source: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let attempt = 0
    let stopped = false

    function connect() {
      source = new EventSource('/api/events')

      source.onopen = () => {
        void onReconnectRef.current()
        attempt = 0
        setState('connected')
      }

      const handle = (type: TaskEvent['type']) => (raw: MessageEvent) => {
        onEventRef.current({ type, task: JSON.parse(raw.data) })
      }
      source.addEventListener('task.created', handle('task.created'))
      source.addEventListener('task.updated', handle('task.updated'))
      source.addEventListener('task.deleted', handle('task.deleted'))

      source.onerror = () => {
        source?.close()
        if (stopped) return
        setState('reconnecting')
        const delay = BACKOFF_SEC[Math.min(attempt, BACKOFF_SEC.length - 1)] * 1000
        attempt += 1
        // EventSource hides the status code, so probe auth before retrying
        void fetch('/api/auth/me', { credentials: 'same-origin' }).then(
          (res) => {
            if (res.status === 401) {
              stopped = true
              notifyAuthExpired()
              return
            }
            if (!stopped) retryTimer = setTimeout(connect, delay)
          },
          () => {
            if (!stopped) retryTimer = setTimeout(connect, delay)
          },
        )
      }
    }

    connect()
    return () => {
      stopped = true
      source?.close()
      if (retryTimer) clearTimeout(retryTimer)
    }
  }, [])

  return state
}
