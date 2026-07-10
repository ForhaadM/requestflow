import { Fragment, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { getAllRequests } from '../api/requests'
import { getReviews, createReview } from '../api/reviews'
import { getUsers } from '../api/auth'
import { StatusBadge, PriorityBadge, DecisionBadge } from '../components/Badge'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { PageHeader } from '../components/PageHeader'
import { FilterDropdown } from '../components/FilterDropdown'
import { BarChart } from '../components/BarChart'
import { formatDateTime } from '../lib/formatDate'
import { REQUEST_TYPES, requestTypeLabel, decisionVerbsFor } from '../lib/requestTypes'

const STATUSES = ['open', 'in-progress', 'approved', 'rejected']
const TYPES = REQUEST_TYPES.map((t) => t.value)

// Same state colors as StatusBadge, reused here so the chart matches the
// rest of the app's status vocabulary instead of a separate chart palette.
const STATUS_COLORS = {
  open: '#2563eb',
  'in-progress': '#f59e0b',
  approved: '#059669',
  rejected: '#dc2626',
}
const STATUS_LABELS = { open: 'Open', 'in-progress': 'In Review', approved: 'Approved', rejected: 'Rejected' }

// Single hue for every bar: type is nominal (position + label already carry
// identity), so color doesn't need to distinguish categories here.
const TYPE_BAR_COLOR = '#4f46e5'

function tally(items, key) {
  return items.reduce((acc, item) => {
    acc[item[key]] = (acc[item[key]] || 0) + 1
    return acc
  }, {})
}

function OverrideRow({ request, token, onOverridden, onCancel }) {
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const verbs = decisionVerbsFor(request.request_type)

  // A rejected request can only be overridden to approved, and vice versa —
  // this row always flips the current decision to its opposite.
  const targetDecision = request.status === 'rejected' ? 'APPROVED' : 'NOT APPROVED'
  const actionLabel = targetDecision === 'APPROVED' ? verbs.positiveAction : verbs.negativeAction
  const buttonColor =
    targetDecision === 'APPROVED'
      ? 'bg-emerald-600 hover:bg-emerald-500'
      : 'bg-red-600 hover:bg-red-500'

  async function handleOverride() {
    setError('')
    if (!comment.trim()) {
      setError('A comment is required when overriding a previous decision.')
      return
    }
    setSubmitting(true)
    try {
      const review = await createReview(token, {
        request_reference: request.request_id,
        decision: targetDecision,
        comment_text: comment.trim(),
      })
      onOverridden(request.request_id, review, targetDecision === 'APPROVED' ? 'approved' : 'rejected')
    } catch (err) {
      setError(err.message || 'Failed to override decision')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <tr className="bg-slate-50">
      <td colSpan={8} className="px-4 py-4">
        <div className="max-w-xl">
          <label className="block text-xs font-medium text-slate-700">
            Reason for override <span className="font-normal text-slate-400">(required)</span>
          </label>
          <textarea
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            autoFocus
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <Alert>{error}</Alert>
          <div className="mt-2 flex gap-2">
            <button
              onClick={handleOverride}
              disabled={submitting}
              className={`cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 ${buttonColor}`}
            >
              {submitting ? 'Overriding…' : `${actionLabel} override`}
            </button>
            <button
              onClick={onCancel}
              disabled={submitting}
              className="cursor-pointer rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      </td>
    </tr>
  )
}

export function AdminDashboardPage() {
  const { token } = useAuth()
  const [requests, setRequests] = useState([])
  const [reviews, setReviews] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [overridingId, setOverridingId] = useState(null)

  useEffect(() => {
    Promise.all([getAllRequests(token), getReviews(token), getUsers()])
      .then(([r, rv, u]) => {
        setRequests(r)
        setReviews(rv)
        setUsers(u)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  function nameFor(userId) {
    return users.find((u) => u.user_id === userId)?.name || `user #${userId}`
  }

  function requestTypeFor(requestId) {
    return requests.find((r) => r.request_id === requestId)?.request_type
  }

  const byStatus = useMemo(() => tally(requests, 'status'), [requests])
  const byType = useMemo(() => tally(requests, 'request_type'), [requests])

  const visibleRequests = useMemo(
    () => (statusFilter === 'all' ? requests : requests.filter((r) => r.status === statusFilter)),
    [requests, statusFilter]
  )

  function handleOverridden(requestId, review, newStatus) {
    setRequests((prev) =>
      prev.map((r) => (r.request_id === requestId ? { ...r, status: newStatus } : r))
    )
    setReviews((prev) => [...prev, review])
    setOverridingId(null)
  }

  if (loading) return <Spinner />

  return (
    <div className="space-y-8">
      <PageHeader
        title="Admin dashboard"
        subtitle="All requests and reviews in the system."
        action={
          <div className="text-right">
            <p className="text-5xl font-semibold tabular-nums text-white">{requests.length}</p>
            <p className="mt-1 text-xs font-medium uppercase tracking-wide text-indigo-100">Total requests</p>
          </div>
        }
      />

      <Alert>{error}</Alert>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Requests by status</h2>
          <p className="mt-1 text-xs text-slate-400">
            "Approved" and "Rejected" cover every outcome (e.g. Resolved/Declined on bug reports too).
          </p>
          <div className="mt-4">
            <BarChart
              ariaLabel="Requests by status"
              data={STATUSES.map((s) => ({
                label: STATUS_LABELS[s],
                value: byStatus[s] || 0,
                color: STATUS_COLORS[s],
              }))}
            />
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Requests by type</h2>
          <div className="mt-4">
            <BarChart
              ariaLabel="Requests by type"
              data={[...TYPES]
                .sort((a, b) => (byType[b] || 0) - (byType[a] || 0))
                .map((t) => ({
                  label: requestTypeLabel(t),
                  value: byType[t] || 0,
                  color: TYPE_BAR_COLOR,
                }))}
            />
          </div>
        </section>
      </div>

      <section>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">All requests</h2>
          <FilterDropdown
            value={statusFilter}
            options={['all', ...STATUSES]}
            onChange={setStatusFilter}
          />
        </div>

        <div className="mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Requester</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Claimed By</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visibleRequests.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    No requests with this status.
                  </td>
                </tr>
              )}
              {visibleRequests.map((r) => (
                <Fragment key={r.request_id}>
                  <tr>
                    <td className="px-4 py-3 text-slate-500">#{r.request_id}</td>
                    <td className="px-4 py-3 text-slate-600">{nameFor(r.requester_reference)}</td>
                    <td className="px-4 py-3 font-medium text-slate-900">{requestTypeLabel(r.request_type)}</td>
                    <td className="px-4 py-3"><PriorityBadge priority={r.priority} /></td>
                    <td className="px-4 py-3"><StatusBadge status={r.status} requestType={r.request_type} /></td>
                    <td className="px-4 py-3 text-slate-500">
                      {r.claimed_by ? nameFor(r.claimed_by) : '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDateTime(r.created_at)}</td>
                    <td className="px-4 py-3">
                      {(r.status === 'rejected' || r.status === 'approved') && (
                        <button
                          onClick={() => setOverridingId(overridingId === r.request_id ? null : r.request_id)}
                          className="cursor-pointer text-sm font-medium text-indigo-600 hover:underline"
                        >
                          {r.status === 'rejected' ? 'Override rejection' : 'Reverse decision'}
                        </button>
                      )}
                    </td>
                  </tr>
                  {overridingId === r.request_id && (
                    <OverrideRow
                      request={r}
                      token={token}
                      onOverridden={handleOverridden}
                      onCancel={() => setOverridingId(null)}
                    />
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">All reviews</h2>
        <div className="mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Request</th>
                <th className="px-4 py-3">Reviewer</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Comment</th>
                <th className="px-4 py-3">Reviewed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reviews.map((rv) => (
                <tr key={rv.review_id}>
                  <td className="px-4 py-3 text-slate-500">#{rv.review_id}</td>
                  <td className="px-4 py-3 text-slate-600">#{rv.request_reference}</td>
                  <td className="px-4 py-3 text-slate-600">{nameFor(rv.reviewer_reference)}</td>
                  <td className="px-4 py-3">
                    <DecisionBadge decision={rv.decision} requestType={requestTypeFor(rv.request_reference)} />
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 text-slate-600">{rv.comment_text || '—'}</td>
                  <td className="px-4 py-3 text-slate-500">{formatDateTime(rv.reviewed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
