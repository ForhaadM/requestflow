import { Fragment, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useUsers } from '../context/UsersContext'
import { getAllRequests } from '../api/requests'
import { getReviews } from '../api/reviews'
import { DecisionBadge } from '../components/Badge'
import { FilterDropdown } from '../components/FilterDropdown'
import { MultiSelectFilter } from '../components/MultiSelectFilter'
import { SearchInput } from '../components/SearchInput'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { PageHeader } from '../components/PageHeader'
import { EmptyState } from '../components/EmptyState'
import { RequestDetailPanel } from '../components/RequestDetailPanel'
import { formatDateTime } from '../lib/formatDate'
import { REQUEST_TYPES, requestTypeLabel } from '../lib/requestTypes'
import { PRIORITY_ORDER, PRIORITY_LABELS } from '../lib/priority'

const FILTER_OPTIONS = ['All', 'Approved', 'Rejected']
const FILTER_TO_DECISION = { Approved: 'APPROVED', Rejected: 'NOT APPROVED' }
const TYPE_OPTIONS = REQUEST_TYPES.map((t) => t.value)

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

export function CompletedReviewsPage() {
  const { token, user } = useAuth()
  const { nameFor: requesterName, emailFor } = useUsers()
  const [reviews, setReviews] = useState([])
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('All')
  const [expandedId, setExpandedId] = useState(null)
  const [search, setSearch] = useState('')
  const [priorityFilter, setPriorityFilter] = useState([])
  const [typeFilter, setTypeFilter] = useState([])

  useEffect(() => {
    setLoading(true)
    setError('')
    // The search/priority/type filters live on the request, not the review,
    // so they're applied server-side via getAllRequests — reviews are then
    // shown only for requests that survive that filtered set.
    Promise.all([
      getReviews(token),
      getAllRequests(token, { search, priority: priorityFilter, request_type: typeFilter }),
    ])
      .then(([rv, req]) => {
        setReviews(rv)
        setRequests(req)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token, search, priorityFilter, typeFilter])

  const visibleReviews = useMemo(() => {
    const matchingRequestIds = new Set(requests.map((r) => r.request_id))
    const sorted = [...reviews]
      .filter((rv) => matchingRequestIds.has(rv.request_reference))
      .sort((a, b) => new Date(b.reviewed_at) - new Date(a.reviewed_at))
    if (filter === 'All') return sorted
    return sorted.filter((rv) => rv.decision === FILTER_TO_DECISION[filter])
  }, [reviews, requests, filter])

  function requestFor(id) {
    return requests.find((r) => r.request_id === id)
  }

  return (
    <div>
      <PageHeader title="Completed reviews" subtitle="Decisions you've made on requests." />

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <SearchInput value={search} onSearch={setSearch} placeholder="Search by ID, requester, or description…" />
        <MultiSelectFilter
          label="Priority"
          value={priorityFilter}
          options={PRIORITY_ORDER}
          optionLabel={(p) => PRIORITY_LABELS[p]}
          onChange={setPriorityFilter}
        />
        <MultiSelectFilter
          label="Type"
          value={typeFilter}
          options={TYPE_OPTIONS}
          optionLabel={requestTypeLabel}
          onChange={setTypeFilter}
        />
        <FilterDropdown label="Decision" value={filter} options={FILTER_OPTIONS} onChange={setFilter} />
      </div>

      <div className="mt-4">
        <Alert>{error}</Alert>
        {loading ? (
          <Spinner />
        ) : visibleReviews.length === 0 ? (
          <EmptyState title="No completed reviews yet." />
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">ID</th>
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
                  const expanded = expandedId === rv.review_id
                  return (
                    <Fragment key={rv.review_id}>
                      <tr
                        onClick={() => setExpandedId(expanded ? null : rv.review_id)}
                        className="cursor-pointer hover:bg-slate-50"
                      >
                        <td className="px-4 py-3 text-slate-500">
                          <span className="flex items-center gap-2">
                            <ChevronIcon expanded={expanded} />
                            {request ? `#${request.request_id}` : '—'}
                          </span>
                        </td>
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
                      {expanded && (
                        <tr className="bg-slate-50">
                          <td colSpan={6} className="px-4 py-4">
                            {request ? (
                              <RequestDetailPanel
                                request={request}
                                token={token}
                                requesterEmail={emailFor(request.requester_reference)}
                                // This route is reviewer-only (see App.jsx), so admin
                                // isn't a case here — just whether this viewer still
                                // holds the claim, matching the backend's
                                // create_comment_for_request authorization.
                                canAddComment={request.claimed_by === user.user_id}
                                currentUserId={user.user_id}
                                resolvedAt={rv.reviewed_at}
                              />
                            ) : (
                              <p className="text-sm text-slate-500">Request details are no longer available.</p>
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
        )}
      </div>
    </div>
  )
}
