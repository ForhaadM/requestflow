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
