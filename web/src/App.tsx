import { useEffect, useState } from 'react'
import { api } from './api'
import { useAuth } from './hooks/useAuth'
import type { Task } from './types'

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

function TaskList({ onLogout }: { onLogout: () => void }) {
  const [tasks, setTasks] = useState<Task[]>([])

  useEffect(() => {
    void api.tasks().then(setTasks)
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-200">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold">Tasks</h1>
          <button onClick={onLogout} className="text-sm text-slate-400 hover:text-slate-200">
            Log out
          </button>
        </div>
        <ul className="space-y-2">
          {tasks.map((task) => (
            <li key={task.id} className="rounded-md border border-slate-800 bg-slate-900 p-3">
              <div className="flex items-center justify-between">
                <span>{task.title}</span>
                <span className="text-xs uppercase text-slate-500">{task.status}</span>
              </div>
            </li>
          ))}
          {tasks.length === 0 && <p className="text-slate-500">No tasks yet.</p>}
        </ul>
      </div>
    </div>
  )
}

export default function App() {
  const { user, loading, logout } = useAuth()

  if (loading) return null
  if (!user) return <LoginGate />
  return <TaskList onLogout={logout} />
}
