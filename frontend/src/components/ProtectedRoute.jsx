import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute({ allowedRoles }) {
  const { token, user, loading } = useAuth()

  if (loading) return <div className="p-8 text-center text-slate-500">Loading…</div>
  if (!token || !user) return <Navigate to="/welcome" replace />
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
