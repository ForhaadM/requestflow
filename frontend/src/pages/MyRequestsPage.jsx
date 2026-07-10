import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getMyRequests, getRequestReviews } from '../api/requests'
import { StatusBadge, PriorityBadge, DecisionBadge } from '../components/Badge'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { PageHeader } from '../components/PageHeader'
import { StatTile } from '../components/StatTile'
import { EmptyState } from '../components/EmptyState'
import { formatDateTime } from '../lib/formatDate'
import { requestTypeLabel } from '../lib/requestTypes'

function ChevronIcon({ expanded }) {
  return (
    <svg
      className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${expanded ? 'rotate-90' : ''}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}

const DECIDED_STATUSES = ['approved', 'rejected']

export function MyRequestsPage() {
  const { token } = useAuth()
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [reviewsById, setReviewsById] = useState({})
  const [reviewsLoading, setReviewsLoading] = useState(false)

  useEffect(() => {
    getMyRequests(token)
      .then(setRequests)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  async function handleToggle(request) {
    const isDecided = DECIDED_STATUSES.includes(request.status)
    if (expandedId === request.request_id) {
      setExpandedId(null)
      return
    }
    setExpandedId(request.request_id)
    if (isDecided && !reviewsById[request.request_id]) {
      setReviewsLoading(true)
      try {
        const reviews = await getRequestReviews(token, request.request_id)
        setReviewsById((prev) => ({ ...prev, [request.request_id]: reviews }))
      } catch (err) {
        setError(err.message)
      } finally {
        setReviewsLoading(false)
      }
    }
  }

  const statusCounts = useMemo(() => {
    const counts = { open: 0, 'in-progress': 0, approved: 0, rejected: 0 }
    for (const r of requests) {
      if (r.status in counts) counts[r.status] += 1
    }
    return counts
  }, [requests])

  return (
    <div>
      <PageHeader title="My requests" subtitle="Everything you've submitted, in one place." />

      <div className="mt-6">
        <Alert>{error}</Alert>
        {loading ? (
          <Spinner />
        ) : requests.length === 0 ? (
          <EmptyState
            title="You haven't submitted any requests yet."
            action={
              <Link
                to="/requests/new"
                className="inline-block rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Create a New Request
              </Link>
            }
          />
        ) : (
          <>
            <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Open" value={statusCounts.open} accent="text-blue-600" />
              <StatTile label="In Review" value={statusCounts['in-progress']} accent="text-amber-600" />
              <StatTile label="Approved" value={statusCounts.approved} accent="text-emerald-600" />
              <StatTile label="Rejected" value={statusCounts.rejected} accent="text-red-600" />
            </div>
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {requests.map((r) => {
                  const expanded = expandedId === r.request_id
                  const isDecided = DECIDED_STATUSES.includes(r.status)
                  return (
                    <Fragment key={r.request_id}>
                      <tr
                        onClick={() => handleToggle(r)}
                        className="cursor-pointer hover:bg-slate-50"
                      >
                        <td className="px-4 py-3 text-slate-500">
                          <span className="flex items-center gap-2">
                            <ChevronIcon expanded={expanded} />#{r.request_id}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-900">{requestTypeLabel(r.request_type)}</td>
                        <td className="max-w-xs truncate px-4 py-3 text-slate-600">{r.description || '—'}</td>
                        <td className="px-4 py-3"><PriorityBadge priority={r.priority} /></td>
                        <td className="px-4 py-3"><StatusBadge status={r.status} requestType={r.request_type} /></td>
                        <td className="px-4 py-3 text-slate-500">{formatDateTime(r.created_at)}</td>
                      </tr>
                      {expanded && (
                        <tr className="bg-slate-50">
                          <td colSpan={6} className="px-4 py-4">
                            {r.urgency_justification && (
                              <div className="mt-2 rounded-md bg-red-50 px-3 py-2 ring-1 ring-inset ring-red-200">
                                <p className="text-xs font-medium text-red-700">Why this was marked Urgent</p>
                                <p className="mt-0.5 text-sm text-red-700">{r.urgency_justification}</p>
                              </div>
                            )}

                            {!isDecided ? (
                              <p className="mt-3 text-sm text-slate-500">
                                No decision yet — this request is still {r.status === 'in-progress' ? 'being reviewed' : 'waiting for a reviewer'}.
                              </p>
                            ) : reviewsLoading && !reviewsById[r.request_id] ? (
                              <div className="mt-3"><Spinner label="Loading decision…" /></div>
                            ) : (
                              <div className="mt-3 space-y-2">
                                {(reviewsById[r.request_id] || []).map((rv) => (
                                  <div key={rv.review_id} className="rounded-md border border-slate-200 bg-white p-3">
                                    <div className="flex items-center justify-between">
                                      <DecisionBadge decision={rv.decision} requestType={r.request_type} />
                                      <span className="text-xs text-slate-400">
                                        {formatDateTime(rv.reviewed_at)}
                                      </span>
                                    </div>
                                    {rv.comment_text && (
                                      <p className="mt-2 text-sm text-slate-600">{rv.comment_text}</p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
