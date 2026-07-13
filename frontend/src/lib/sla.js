// Must stay in sync with backend/sla.py — SLA window per priority, computed
// from created_at rather than persisted.
export const SLA_WINDOWS_MS = {
  P0: 2 * 60 * 60 * 1000,
  P1: 12 * 60 * 60 * 1000,
  P2: 7 * 24 * 60 * 60 * 1000,
  P3: 14 * 24 * 60 * 60 * 1000,
}

// "Approaching" once 25% or less of the window remains.
const WARNING_THRESHOLD = 0.25

// The backend sends naive timestamps (no trailing Z/offset) that are always
// UTC (see backend/timeutils.py). A bare `new Date("2026-...T...")` parses
// that as *local* time instead, silently shifting the deadline by the
// viewer's UTC offset — append Z so it's parsed as UTC like it actually is.
function parseUtc(value) {
  if (value instanceof Date) return value
  const hasTimezone = /Z|[+-]\d\d:\d\d$/.test(value)
  return new Date(hasTimezone ? value : `${value}Z`)
}

export function getSlaStatus(priority, createdAt, now = new Date()) {
  const windowMs = SLA_WINDOWS_MS[priority]
  const created = parseUtc(createdAt)
  const deadline = new Date(created.getTime() + windowMs)
  const remainingMs = deadline.getTime() - now.getTime()

  let status
  if (remainingMs <= 0) {
    status = 'breached'
  } else if (remainingMs <= windowMs * WARNING_THRESHOLD) {
    status = 'warning'
  } else {
    status = 'ok'
  }

  return { deadline, remainingMs, status }
}

function formatDuration(ms) {
  const abs = Math.abs(ms)
  const minutes = Math.round(abs / 60000)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.round(hours / 24)
  return `${days}d`
}

export function formatSlaRemaining({ remainingMs, status }) {
  if (status === 'breached') return `Breached by ${formatDuration(remainingMs)}`
  return `${formatDuration(remainingMs)} left`
}

// For an already-resolved request: a fixed past outcome, not a live
// countdown — "3h left" would be misleading once the ticket is closed.
export function formatSlaOutcome(remainingMs) {
  return remainingMs >= 0 ? 'Met SLA' : `Missed SLA by ${formatDuration(remainingMs)}`
}
