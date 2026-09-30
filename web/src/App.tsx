import { Board } from './components/Board'
import { useAuth } from './hooks/useAuth'
import { useEventStream } from './hooks/useEventStream'
import { useTasks } from './hooks/useTasks'

function LoginGate() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-200">
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-8 text-center">
        <p className="text-lg font-medium">Not signed in</p>
        <p className="mt-2 text-slate-400">Send /login to the bot in Telegram to open a link here.</p>
      </div>
    </div>
  )
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const { tasks, refetch, updateStatus, retry, applyEvent } = useTasks()
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
        <Board
          tasks={tasks}
          onStatusChange={(id, status) => void updateStatus(id, status).catch(() => {})}
          onRetry={(id) => void retry(id).catch(() => {})}
        />
      </div>
    </div>
  )
}

export default function App() {
  const { user, loading, logout } = useAuth()

  if (loading) return null
  if (!user) return <LoginGate />
  return <Dashboard onLogout={logout} />
}
