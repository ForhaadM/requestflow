import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute({ allowedRoles }) {
  const { token, user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <div className="p-8 text-center text-slate-500">Loading…</div>
  if (!token || !user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
