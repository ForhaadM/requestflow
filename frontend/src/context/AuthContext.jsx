import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { login as apiLogin, getUsers } from '../api/auth'

const AuthContext = createContext(null)

const TOKEN_KEY = 'requestflow_token'

// JWTs are only base64url-encoded, not encrypted, so decoding the payload
// client-side to read `sub` (the user id) is safe — it reveals nothing the
// server doesn't already hand back, and every real permission check still
// happens server-side on each request.
function decodeUserId(token) {
  try {
    const payload = token.split('.')[1]
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    const { sub } = JSON.parse(json)
    return Number(sub)
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  const loadUser = useCallback(async (tok) => {
    if (!tok) {
      setUser(null)
      setLoading(false)
      return
    }
    const userId = decodeUserId(tok)
    try {
      const users = await getUsers()
      const match = users.find((u) => u.user_id === userId)
      if (!match) throw new Error('User not found')
      setUser({ user_id: match.user_id, name: match.name, email: match.email, role: match.role })
    } catch {
      // Token is invalid/expired or the backend is unreachable — treat as logged out.
      localStorage.removeItem(TOKEN_KEY)
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUser(token)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function signIn(email, password) {
    const { access_token } = await apiLogin({ email, password })
    localStorage.setItem(TOKEN_KEY, access_token)
    setToken(access_token)
    setLoading(true)
    await loadUser(access_token)
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }

  // Fired by apiFetch on any 401 (expired/invalid token). Signs out and sends
  // the user back to login instead of leaving a raw "Invalid Token" error
  // sitting in whatever page they were on.
  useEffect(() => {
    function handleUnauthorized() {
      signOut()
      if (location.pathname !== '/login' && location.pathname !== '/register') {
        navigate('/login', { replace: true })
      }
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  return (
    <AuthContext.Provider value={{ token, user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
