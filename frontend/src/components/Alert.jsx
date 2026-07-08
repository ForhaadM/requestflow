export function Alert({ type = 'error', children }) {
  if (!children) return null
  const styles =
    type === 'error'
      ? 'bg-red-50 text-red-700 ring-red-200'
      : 'bg-emerald-50 text-emerald-700 ring-emerald-200'
  return (
    <div className={`rounded-md px-4 py-3 text-sm ring-1 ring-inset ${styles}`} role="alert">
      {children}
    </div>
  )
}
