import { useEffect, useState } from 'react'

function SearchIcon() {
  return (
    <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 21l-4.35-4.35M17 10.5A6.5 6.5 0 114 10.5a6.5 6.5 0 0113 0z"
      />
    </svg>
  )
}

// Debounced free-text search box. Debounced (not fired on every keystroke)
// since `onSearch` triggers a server round-trip (search is applied in SQL,
// not filtered client-side against an already-fetched list).
export function SearchInput({ value, onSearch, placeholder = 'Search…' }) {
  const [draft, setDraft] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      if (draft !== value) onSearch(draft)
    }, 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])

  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center">
        <SearchIcon />
      </span>
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={placeholder}
        className="w-64 rounded-lg border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-sm text-slate-700 shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      />
    </div>
  )
}
