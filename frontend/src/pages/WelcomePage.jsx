import { Link } from 'react-router-dom'

const FEATURES = [
  {
    title: 'Submit requests in minutes',
    description: 'Hardware, software, access, bugs, and more — one simple form for everything.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    ),
  },
  {
    title: 'Track status in real time',
    description: "See exactly where a request stands, from open to resolved — no more guessing.",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    ),
  },
  {
    title: 'Built-in review workflow',
    description: 'Reviewers claim, approve, or reject with a full audit trail on every decision.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    ),
  },
  {
    title: 'AI assistant built in',
    description: 'Describe what you need in plain English and let the assistant create the request for you.',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h4m8-2a8 8 0 11-16 0 8 8 0 0116 0z" />
    ),
  },
]

export function WelcomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-50 via-white to-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <span className="text-lg font-semibold tracking-tight text-slate-900">RequestFlow</span>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:text-indigo-600"
          >
            Sign in
          </Link>
          <Link
            to="/register"
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700"
          >
            Create an account
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24 pt-12 sm:pt-20">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
            Internal requests,{' '}
            <span className="bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">
              handled
            </span>
          </h1>
          <p className="mt-4 text-lg text-slate-600">
            Submit, track, and resolve hardware, software, access, and support requests — all in one
            place, with a clear review trail every step of the way.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Link
              to="/register"
              className="rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700"
            >
              Get started
            </Link>
            <Link
              to="/login"
              className="rounded-md border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Sign in
            </Link>
          </div>
        </div>

        <div className="mt-20 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="h-5 w-5">
                  {f.icon}
                </svg>
              </div>
              <h3 className="mt-4 text-sm font-semibold text-slate-900">{f.title}</h3>
              <p className="mt-1.5 text-sm text-slate-500">{f.description}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
