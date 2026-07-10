export function EmptyState({ title, action }) {
  return (
    <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50/40 p-10 text-center">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        className="mx-auto h-10 w-10 text-indigo-300"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7.5l9-4.5 9 4.5M3 7.5l9 4.5m-9-4.5v9l9 4.5m0-9l9-4.5m-9 4.5v9m9-13.5v9l-9 4.5" />
      </svg>
      <p className="mt-3 text-sm text-slate-500">{title}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
