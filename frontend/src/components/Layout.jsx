import { Outlet } from 'react-router-dom'
import { NavBar } from './NavBar'
import { ChatWidget } from './ChatWidget'
import { useAuth } from '../context/AuthContext'

export function Layout() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-50/60 via-slate-50 to-slate-50">
      <NavBar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
      {/* Flowy Assistant helps requesters create/check their own requests — not
          meaningful for reviewers/admins, so it's hidden for those roles here,
          same pattern as NAV_VISIBILITY in navVisibility.js. */}
      {user?.role === 'requester' && <ChatWidget />}
    </div>
  )
}
