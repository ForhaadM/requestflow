import { useState } from 'react'

// Tracks which column is currently sorting the table, plus each column's own
// remembered direction — so switching to sort by a different column doesn't
// reset the direction you'd left the other column at. Clicking the active
// column toggles it; clicking any other column switches to it, resuming
// whatever direction it was last set to (default 'asc').
export function useColumnSort(defaultColumn, columns) {
  const [activeColumn, setActiveColumn] = useState(defaultColumn)
  const [directions, setDirections] = useState(() =>
    Object.fromEntries(columns.map((c) => [c, 'asc']))
  )

  function toggleColumn(column) {
    if (column === activeColumn) {
      setDirections((prev) => ({ ...prev, [column]: prev[column] === 'asc' ? 'desc' : 'asc' }))
    } else {
      setActiveColumn(column)
    }
  }

  return { activeColumn, direction: directions[activeColumn], toggleColumn }
}
