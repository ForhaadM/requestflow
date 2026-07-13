// Standard up/down sort-direction arrows (not a chevron, which this app
// already uses elsewhere for expand/collapse — a different affordance).
// Unsorted columns show a neutral up-and-down arrow; the active column shows
// a single arrow pointing the direction it's currently sorted.
function SortArrow({ active, direction }) {
  const className = `h-3.5 w-3.5 shrink-0 ${active ? 'text-slate-600' : 'text-slate-300'}`
  const svgProps = { className, fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }
  const pathProps = { strokeLinecap: 'round', strokeLinejoin: 'round', strokeWidth: 2 }

  if (!active) {
    return (
      <svg {...svgProps}>
        <path {...pathProps} d="m3 8 4-4 4 4" />
        <path {...pathProps} d="M7 4v16" />
        <path {...pathProps} d="m21 16-4 4-4-4" />
        <path {...pathProps} d="M17 20V4" />
      </svg>
    )
  }

  return direction === 'desc' ? (
    <svg {...svgProps}>
      <path {...pathProps} d="M12 5v14" />
      <path {...pathProps} d="m19 12-7 7-7-7" />
    </svg>
  ) : (
    <svg {...svgProps}>
      <path {...pathProps} d="m5 12 7-7 7 7" />
      <path {...pathProps} d="M12 19V5" />
    </svg>
  )
}

export function SortableColumnHeader({ label, column, activeColumn, direction, onToggle }) {
  const active = column === activeColumn
  return (
    <th className="px-4 py-3">
      <button
        type="button"
        onClick={() => onToggle(column)}
        className={`flex cursor-pointer items-center gap-1 hover:text-slate-700 ${active ? 'text-slate-700' : ''}`}
      >
        {label}
        <SortArrow active={active} direction={direction} />
      </button>
    </th>
  )
}
