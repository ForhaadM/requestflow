import { Outlet } from 'react-router-dom'
import { NavBar } from './NavBar'
import { ChatWidget } from './ChatWidget'

export function Layout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
      <ChatWidget />
    </div>
  )
}
