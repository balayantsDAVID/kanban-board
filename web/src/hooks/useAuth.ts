import { useCallback, useEffect, useState } from 'react'
import { AUTH_EXPIRED, ApiError, api } from '../api'
import type { User } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [loginError, setLoginError] = useState<string | null>(null)

  useEffect(() => {
    async function init() {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('token')
      if (token) {
        try {
          await api.exchange(token)
        } catch {
          setLoginError('Ссылка устарела. Отправь /login боту заново.')
        } finally {
          // Drop the token from the URL so it isn't logged or bookmarked.
          window.history.replaceState({}, '', window.location.pathname)
        }
      }
      try {
        setUser(await api.me())
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) {
          setLoginError('Не удалось связаться с сервером. Обнови страницу.')
        }
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    void init()
  }, [])

  useEffect(() => {
    const onExpired = () => setUser(null)
    window.addEventListener(AUTH_EXPIRED, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED, onExpired)
  }, [])

  const logout = useCallback(async () => {
    await api.logout()
    setUser(null)
  }, [])

  return { user, loading, loginError, logout }
}
