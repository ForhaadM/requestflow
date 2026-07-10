// All timestamps in the app are shown in US Eastern time regardless of the
// viewer's local timezone, since this is an internal tool for one org.
const TIME_ZONE = 'America/New_York'

export function formatDateTime(value) {
  if (!value) return '—'
  return `${new Date(value).toLocaleString('en-US', {
    timeZone: TIME_ZONE,
    dateStyle: 'medium',
    timeStyle: 'short',
  })} ET`
}

export function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-US', {
    timeZone: TIME_ZONE,
  })
}

// Coarse "how long ago" for surfacing in duplicate-request warnings, e.g.
// "submitted 2 days ago" — doesn't need to be precise to the minute.
export function formatRelativeDays(value) {
  if (!value) return ''
  const days = Math.floor((Date.now() - new Date(value).getTime()) / (1000 * 60 * 60 * 24))
  if (days <= 0) return 'today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}
