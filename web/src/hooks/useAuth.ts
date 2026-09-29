import { useEffect, useState } from 'react'
import { ApiError, api } from '../api'
import type { User } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function init() {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('token')
      if (token) {
        try {
          await api.exchange(token)
        } finally {
          // Drop the token from the URL so it isn't logged or bookmarked.
          window.history.replaceState({}, '', window.location.pathname)
        }
      }
      try {
        setUser(await api.me())
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) throw err
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    void init()
  }, [])

  const logout = async () => {
    await api.logout()
    setUser(null)
  }

  return { user, loading, logout }
}
