// Shown in the viewer's own local timezone (whatever their machine is set
// to) rather than a fixed zone — omitting `timeZone` below defaults
// `toLocaleString`/`toLocaleDateString` to the browser's local zone.
// `timeZoneName: 'short'` appends the correct abbreviation for that zone
// (e.g. "PDT", "EDT") instead of a hardcoded, potentially-wrong one.
// Intl.DateTimeFormat throws if `dateStyle`/`timeStyle` are combined with any
// other option (including timeZoneName), so this spells out the individual
// fields instead of using those two shorthands.
export function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}

export function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-US')
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
