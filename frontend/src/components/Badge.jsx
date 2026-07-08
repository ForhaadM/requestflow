import { PRIORITY_LABELS } from '../lib/priority'
import { outcomeLabel } from '../lib/requestTypes'

const STATUS_LABELS = {
  open: 'Open',
  'in-progress': 'In Review',
  approved: 'Approved',
  rejected: 'Rejected',
  resolved: 'Resolved',
  closed: 'Closed',
}

const STATUS_STYLES = {
  open: 'bg-blue-50 text-blue-700 ring-blue-200',
  'in-progress': 'bg-amber-50 text-amber-700 ring-amber-200',
  approved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  rejected: 'bg-red-50 text-red-700 ring-red-200',
  resolved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  closed: 'bg-slate-100 text-slate-600 ring-slate-200',
}

const PRIORITY_STYLES = {
  P0: 'bg-red-50 text-red-700 ring-red-200',
  P1: 'bg-orange-50 text-orange-700 ring-orange-200',
  P2: 'bg-yellow-50 text-yellow-700 ring-yellow-200',
  P3: 'bg-slate-50 text-slate-600 ring-slate-200',
}

const DECISION_LABELS = {
  APPROVED: 'Approved',
  'NOT APPROVED': 'Rejected',
}

const DECISION_STYLES = {
  APPROVED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  'NOT APPROVED': 'bg-red-50 text-red-700 ring-red-200',
}

function Badge({ label, className }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  )
}

export function StatusBadge({ status, requestType }) {
  let label = STATUS_LABELS[status] || status
  if (requestType && (status === 'approved' || status === 'rejected')) {
    label = outcomeLabel(requestType, status === 'approved' ? 'positive' : 'negative')
  }
  return <Badge label={label} className={STATUS_STYLES[status] || STATUS_STYLES.closed} />
}

export function PriorityBadge({ priority }) {
  return (
    <Badge
      label={PRIORITY_LABELS[priority] || priority}
      className={PRIORITY_STYLES[priority] || PRIORITY_STYLES.P3}
    />
  )
}

export function DecisionBadge({ decision, requestType }) {
  const label = requestType
    ? outcomeLabel(requestType, decision === 'APPROVED' ? 'positive' : 'negative')
    : DECISION_LABELS[decision] || decision
  return (
    <Badge
      label={label}
      className={DECISION_STYLES[decision] || 'bg-slate-100 text-slate-600 ring-slate-200'}
    />
  )
}
