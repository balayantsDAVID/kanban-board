import { useEffect, useRef, useState } from 'react'
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
    let everConnected = false

    function connect() {
      source = new EventSource('/api/events')

      source.onopen = () => {
        if (everConnected) {
          void onReconnectRef.current()
        }
        everConnected = true
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
        retryTimer = setTimeout(connect, delay)
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
