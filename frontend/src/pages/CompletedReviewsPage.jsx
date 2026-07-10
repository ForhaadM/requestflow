import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useUsers } from '../context/UsersContext'
import { getAllRequests } from '../api/requests'
import { getReviews } from '../api/reviews'
import { DecisionBadge } from '../components/Badge'
import { FilterDropdown } from '../components/FilterDropdown'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { PageHeader } from '../components/PageHeader'
import { EmptyState } from '../components/EmptyState'
import { formatDateTime } from '../lib/formatDate'
import { requestTypeLabel } from '../lib/requestTypes'

const FILTER_OPTIONS = ['All', 'Approved', 'Rejected']
const FILTER_TO_DECISION = { Approved: 'APPROVED', Rejected: 'NOT APPROVED' }

export function CompletedReviewsPage() {
  const { token } = useAuth()
  const { nameFor: requesterName } = useUsers()
  const [reviews, setReviews] = useState([])
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('All')

  useEffect(() => {
    Promise.all([getReviews(token), getAllRequests(token)])
      .then(([rv, req]) => {
        setReviews(rv)
        setRequests(req)
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

  if (loading) return <Spinner />

  return (
    <div>
      <PageHeader
        title="Completed reviews"
        subtitle="Decisions you've made on requests."
        action={
          <div className="text-right">
            <FilterDropdown label="Decision" value={filter} options={FILTER_OPTIONS} onChange={setFilter} />
            <p className="mt-1 text-xs text-indigo-100">Covers Resolved/Declined outcomes too</p>
          </div>
        }
      />

      <div className="mt-6">
        <Alert>{error}</Alert>
        {visibleReviews.length === 0 ? (
          <EmptyState title="No completed reviews yet." />
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
