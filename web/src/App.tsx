import { useState } from 'react'
import { Board } from './components/Board'
import { useAuth } from './hooks/useAuth'
import { useEventStream } from './hooks/useEventStream'
import { useTasks } from './hooks/useTasks'

function NewTaskForm({ onCreate }: { onCreate: (title: string) => void }) {
  const [title, setTitle] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) return
    onCreate(trimmed)
    setTitle('')
  }

  return (
    <form onSubmit={submit} className="mb-4 flex gap-2">
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="New task"
        className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-500"
      />
      <button
        type="submit"
        className="rounded bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
      >
        Add
      </button>
    </form>
  )
}

function LoginGate({ error }: { error: string | null }) {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-200">
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-8 text-center">
        <p className="text-lg font-medium">Not signed in</p>
        <p className="mt-2 text-slate-400">Send /login to the bot in Telegram to open a link here.</p>
        {error && <p className="mt-3 text-sm text-amber-400">{error}</p>}
      </div>
    </div>
  )
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const {
    tasks,
    loading,
    error,
    clearError,
    refetch,
    updateStatus,
    createTask,
    deleteTask,
    retry,
    applyEvent,
  } = useTasks()
  const connection = useEventStream(applyEvent, refetch)

  const counts = {
    pending: tasks.filter((t) => t.status === 'pending').length,
    in_progress: tasks.filter((t) => t.status === 'in_progress').length,
    completed: tasks.filter((t) => t.status === 'completed').length,
  }

  return (
    <div className="min-h-screen bg-slate-950 p-4 text-slate-200 sm:p-6">
      <div className="mx-auto max-w-5xl">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">Tasks</h1>
            <p className="text-xs text-slate-500">
              {counts.pending} pending · {counts.in_progress} in progress · {counts.completed} done
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`flex items-center gap-1.5 text-xs ${
                connection === 'connected' ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  connection === 'connected' ? 'bg-emerald-400' : 'animate-pulse bg-amber-400'
                }`}
              />
              {connection === 'connected' ? 'Live' : 'Reconnecting…'}
            </span>
            <button onClick={onLogout} className="text-sm text-slate-400 hover:text-slate-200">
              Log out
            </button>
          </div>
        </header>
        {error && (
          <div className="mb-4 flex items-center justify-between rounded border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
            <span>{error}</span>
            <button onClick={clearError} className="ml-3 text-red-400 hover:text-red-200">
              ✕
            </button>
          </div>
        )}
        {loading && <p className="mb-4 text-sm text-slate-500">Loading…</p>}
        <NewTaskForm onCreate={(title) => void createTask(title)} />
        <Board
          tasks={tasks}
          onStatusChange={(id, status) => void updateStatus(id, status)}
          onRetry={(id) => void retry(id)}
          onDelete={(id) => void deleteTask(id)}
        />
      </div>
    </div>
  )
}

export default function App() {
  const { user, loading, loginError, logout } = useAuth()

  if (loading) return <div className="h-screen bg-slate-950" />
  if (!user) return <LoginGate error={loginError} />
  return <Dashboard onLogout={logout} />
}
