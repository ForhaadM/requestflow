import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const linkClass = ({ isActive }) =>
  `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

export function NavBar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    signOut()
    navigate('/login')
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="text-lg font-semibold tracking-tight text-slate-900">RequestFlow</span>
          <nav className="flex items-center gap-1">
            {(user?.role === 'requester' || user?.role === 'admin') && (
              <>
                <NavLink to="/requests/new" className={linkClass}>New Request</NavLink>
                <NavLink to="/requests/mine" className={linkClass}>My Requests</NavLink>
              </>
            )}
            {(user?.role === 'reviewer' || user?.role === 'admin') && (
              <NavLink to="/review" end className={linkClass}>Review Queue</NavLink>
            )}
            {user?.role === 'reviewer' && (
              <NavLink to="/review/completed" className={linkClass}>Completed Reviews</NavLink>
            )}
            {user?.role === 'admin' && (
              <NavLink to="/admin" className={linkClass}>Admin Dashboard</NavLink>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <span className="text-sm text-slate-600">
              <span className="font-medium text-slate-900">{user.name}</span>{' '}
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs uppercase tracking-wide text-slate-500">
                {user.role}
              </span>
            </span>
          )}
          <button
            onClick={handleLogout}
            className="cursor-pointer rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Log out
          </button>
        </div>
      </div>
    </header>
  )
}
