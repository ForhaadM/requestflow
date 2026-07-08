// Horizontal bar chart: bars ≤24px thick, 4px rounded tip / square baseline,
// direct value labels at the tip (so no separate legend/table is needed for
// a single-series chart — the label IS the data).
export function BarChart({ data, ariaLabel }) {
  const max = Math.max(...data.map((d) => d.value), 1)

  return (
    <div role="img" aria-label={ariaLabel} className="space-y-2.5">
      {data.map((d) => {
        const pct = (d.value / max) * 100
        return (
          <div key={d.label} className="group flex items-center gap-3">
            <div className="w-40 shrink-0 truncate text-xs text-slate-600" title={d.label}>
              {d.label}
            </div>
            <div className="h-5 flex-1">
              <div
                className="h-5 rounded-r-[4px] transition-[width] duration-300 ease-in-out group-hover:brightness-90"
                style={{ width: `${pct}%`, minWidth: d.value > 0 ? '4px' : 0, backgroundColor: d.color }}
              />
            </div>
            <div className="w-6 shrink-0 text-right text-xs font-medium tabular-nums text-slate-700">
              {d.value}
            </div>
          </div>
        )
      })}
    </div>
  )
}
