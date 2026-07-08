import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <h1 className="text-3xl font-semibold text-slate-900">404</h1>
      <p className="mt-2 text-sm text-slate-500">Page not found.</p>
      <Link to="/" className="mt-4 text-sm font-medium text-slate-900 hover:underline">
        Go home
      </Link>
    </div>
  )
}
