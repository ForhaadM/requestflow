import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { getAllRequests } from '../api/requests'
import { getReviews } from '../api/reviews'
import { getUsers } from '../api/auth'
import { DecisionBadge } from '../components/Badge'
import { FilterDropdown } from '../components/FilterDropdown'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { formatDateTime } from '../lib/formatDate'
import { requestTypeLabel } from '../lib/requestTypes'

const FILTER_OPTIONS = ['All', 'Approved', 'Rejected']
const FILTER_TO_DECISION = { Approved: 'APPROVED', Rejected: 'NOT APPROVED' }

export function CompletedReviewsPage() {
  const { token } = useAuth()
  const [reviews, setReviews] = useState([])
  const [requests, setRequests] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('All')

  useEffect(() => {
    Promise.all([getReviews(token), getAllRequests(token), getUsers()])
      .then(([rv, req, u]) => {
        setReviews(rv)
        setRequests(req)
        setUsers(u)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  const visibleReviews = useMemo(() => {
    const sorted = [...reviews].sort(
      (a, b) => new Date(b.reviewed_at) - new Date(a.reviewed_at)
    )
    if (filter === 'All') return sorted
    return sorted.filter((rv) => rv.decision === FILTER_TO_DECISION[filter])
  }, [reviews, filter])

  function requestFor(id) {
    return requests.find((r) => r.request_id === id)
  }

  function requesterName(userId) {
    return users.find((u) => u.user_id === userId)?.name || `user #${userId}`
  }

  if (loading) return <Spinner />

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Completed reviews</h1>
          <p className="mt-1 text-sm text-slate-500">Decisions you've made on requests.</p>
        </div>
        <div className="text-right">
          <FilterDropdown label="Decision" value={filter} options={FILTER_OPTIONS} onChange={setFilter} />
          <p className="mt-1 text-xs text-slate-400">Covers Resolved/Declined outcomes too</p>
        </div>
      </div>

      <div className="mt-6">
        <Alert>{error}</Alert>
        {visibleReviews.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            No completed reviews yet.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Requester</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Decision</th>
                  <th className="px-4 py-3">Comment</th>
                  <th className="px-4 py-3">Reviewed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibleReviews.map((rv) => {
                  const request = requestFor(rv.request_reference)
                  return (
                    <tr key={rv.review_id}>
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {request ? requesterName(request.requester_reference) : '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {request ? requestTypeLabel(request.request_type) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <DecisionBadge decision={rv.decision} requestType={request?.request_type} />
                      </td>
                      <td className="max-w-xs truncate px-4 py-3 text-slate-600">{rv.comment_text || '—'}</td>
                      <td className="px-4 py-3 text-slate-500">{formatDateTime(rv.reviewed_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
