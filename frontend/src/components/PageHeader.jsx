export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex flex-col gap-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 px-6 py-6 text-white shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-indigo-100">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
