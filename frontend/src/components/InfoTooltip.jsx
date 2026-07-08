export function InfoTooltip({ title, items }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        tabIndex={0}
        aria-label={`Examples for ${title}`}
        className="flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-600 hover:bg-slate-300"
      >
        i
      </button>
      <div className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 w-60 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
        <p className="font-semibold text-slate-900">{title} examples</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </span>
  )
}
