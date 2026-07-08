// Backend stores P0-P3; these are just the display labels + sort order.
export const PRIORITY_ORDER = ['P0', 'P1', 'P2', 'P3']

export const PRIORITY_LABELS = {
  P0: 'Urgent',
  P1: 'High',
  P2: 'Medium',
  P3: 'Low',
}

export function priorityRank(priority) {
  const rank = PRIORITY_ORDER.indexOf(priority)
  return rank === -1 ? PRIORITY_ORDER.length : rank
}
