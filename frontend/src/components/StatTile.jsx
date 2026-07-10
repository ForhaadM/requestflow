export function StatTile({ label, value, accent = 'text-slate-500' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      <p className={`mt-1 text-xs font-medium uppercase tracking-wide ${accent}`}>{label}</p>
    </div>
  )
}
