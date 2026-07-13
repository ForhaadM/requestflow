import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { getUsers } from '../api/auth'
import { useAuth } from './AuthContext'

const UsersContext = createContext(null)

// Shares the reviewer/admin-only user directory (id -> name/email/role)
// across every page that needs it, instead of each page independently
// calling GET /users. Fetches lazily on first use (via useUsers below) so
// pages that never need the directory (e.g. requester-only pages) don't
// trigger the call at all.
export function UsersProvider({ children }) {
  const { token } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // A ref (not state) so the guard below is checked-and-set synchronously:
  // two consumers mounting in the same commit both call ensureLoaded()
  // before either state update has re-rendered, so a state-based guard lets
  // both slip through and fire GET /users twice.
  const fetchState = useRef('idle') // 'idle' | 'loading' | 'loaded'

  // A token change (login as a different user, or logout) invalidates the
  // cached directory so it's re-fetched on next use instead of leaking a
  // previous session's data across a client-side login switch.
  useEffect(() => {
    fetchState.current = 'idle'
    setUsers([])
  }, [token])

  const ensureLoaded = useCallback(() => {
    if (fetchState.current !== 'idle' || !token) return
    fetchState.current = 'loading'
    setLoading(true)
    setError('')
    getUsers(token)
      .then((data) => {
        setUsers(data)
        fetchState.current = 'loaded'
      })
      .catch((err) => {
        setError(err.message || 'Failed to load users')
        fetchState.current = 'idle' // allow a retry on next use
      })
      .finally(() => setLoading(false))
  }, [token])

  function nameFor(userId) {
    return users.find((u) => u.user_id === userId)?.name || `user #${userId}`
  }

  function emailFor(userId) {
    return users.find((u) => u.user_id === userId)?.email || null
  }

  return (
    <UsersContext.Provider value={{ users, loading, error, ensureLoaded, nameFor, emailFor }}>
      {children}
    </UsersContext.Provider>
  )
}

export function useUsers() {
  const ctx = useContext(UsersContext)
  if (!ctx) throw new Error('useUsers must be used within a UsersProvider')

  useEffect(() => {
    ctx.ensureLoaded()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.ensureLoaded])

  return ctx
}
