import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { login as apiLogin, getCurrentUser } from '../api/auth'

const AuthContext = createContext(null)

const TOKEN_KEY = 'requestflow_token'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  // True only right after an explicit signIn() call (not when a token is
  // restored from localStorage on page load) — lets the chat widget auto-open
  // once per login without reopening on every navigation or page refresh.
  const [justLoggedIn, setJustLoggedIn] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const loadUser = useCallback(async (tok) => {
    if (!tok) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const profile = await getCurrentUser(tok)
      setUser({ user_id: profile.user_id, name: profile.name, email: profile.email, role: profile.role })
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
    setJustLoggedIn(true)
  }

  function clearJustLoggedIn() {
    setJustLoggedIn(false)
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
    setJustLoggedIn(false)
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
    <AuthContext.Provider value={{ token, user, loading, signIn, signOut, justLoggedIn, clearJustLoggedIn }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
