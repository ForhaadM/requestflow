import { Fragment, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getMyRequests, getMyRequestsSummary, getRequestReviews, cancelRequest } from '../api/requests'
import { StatusBadge, PriorityBadge, DecisionBadge, SlaBadge } from '../components/Badge'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { PageHeader } from '../components/PageHeader'
import { StatTile } from '../components/StatTile'
import { EmptyState } from '../components/EmptyState'
import { RequestComments } from '../components/RequestComments'
import { SortableColumnHeader } from '../components/SortableColumnHeader'
import { FilterDropdown } from '../components/FilterDropdown'
import { Pagination } from '../components/Pagination'
import { formatDateTime } from '../lib/formatDate'
import { requestTypeLabel } from '../lib/requestTypes'
import { useColumnSort } from '../lib/useColumnSort'

const PAGE_SIZE = 25

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
// A request can only be withdrawn while it's still unclaimed — once it's
// in-progress a reviewer is actively working it, so cancelling out from
// under them isn't offered. Mirrors the same rule enforced server-side in
// cancel_request_for_user.
const CANCELLABLE_STATUSES = ['open']
const STATUSES = ['open', 'in-progress', 'approved', 'rejected', 'cancelled']

export function MyRequestsPage() {
  const { token, user } = useAuth()
  const { id } = useParams()
  // /requests/:id deep-links here (e.g. from an email notification) to
  // auto-expand one specific request; /requests/mine has no :id and this
  // stays null, leaving the page's normal browse behavior untouched.
  const targetRequestId = id ? Number(id) : null
  const [requests, setRequests] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [page, setPage] = useState(1)
  const [summary, setSummary] = useState({ total: 0, by_status: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [expandedId, setExpandedId] = useState(null)
  const [reviewsById, setReviewsById] = useState({})
  const [reviewsLoading, setReviewsLoading] = useState(false)
  const [cancellingId, setCancellingId] = useState(null)
  const [cancelSubmitting, setCancelSubmitting] = useState(false)
  const [cancelError, setCancelError] = useState('')
  const rowRefs = useRef({})

  const { activeColumn, direction, toggleColumn } = useColumnSort('created', ['priority', 'created'])

  function load() {
    setLoading(true)
    getMyRequests(token, {
      status: statusFilter,
      page,
      page_size: PAGE_SIZE,
      sort: activeColumn,
      sort_dir: direction,
    })
      .then((response) => {
        setRequests(response.items)
        setTotal(response.total)
        setTotalPages(response.total_pages)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  function loadSummary() {
    getMyRequestsSummary(token)
      .then(setSummary)
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, statusFilter, activeColumn, direction, page])

  useEffect(() => {
    loadSummary()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  // Changing the status filter or sort column should show page 1 of the new
  // result set, not whatever page the previous view happened to be on.
  useEffect(() => {
    setPage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, activeColumn, direction])

  // A request created through the chat widget (which stays mounted across
  // navigation, unlike the New Request form's own page) broadcasts this
  // event instead of this page having any other way to learn about it.
  useEffect(() => {
    function handleChanged() {
      load()
      loadSummary()
    }
    window.addEventListener('requests:changed', handleChanged)
    return () => window.removeEventListener('requests:changed', handleChanged)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, statusFilter, activeColumn, direction, page])

  // requests is always scoped to the current user server-side (GET
  // /requests/me), so a :id belonging to someone else simply never shows up
  // here — there's no separate authorization check to get wrong, and no way
  // for this to leak whether that ID even exists. Note: since the list is
  // now paginated, this only finds a target that happens to be on the
  // current page/filter/sort — in practice a notification link almost
  // always points at a recently created/reviewed request, which sorts onto
  // page 1 by default.
  const targetNotFound =
    targetRequestId != null && !loading && !requests.some((r) => r.request_id === targetRequestId)

  useEffect(() => {
    if (targetRequestId == null || loading || expandedId === targetRequestId) return
    const match = requests.find((r) => r.request_id === targetRequestId)
    if (match) handleToggle(match)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetRequestId, loading, requests, expandedId])

  useEffect(() => {
    if (targetRequestId != null && expandedId === targetRequestId) {
      // jsdom (unit tests) doesn't implement scrollIntoView at all.
      rowRefs.current[targetRequestId]?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    }
  }, [expandedId, targetRequestId])

  async function handleToggle(request) {
    const isDecided = DECIDED_STATUSES.includes(request.status)
    // Leaving this row (or moving to a different one) shouldn't leave a
    // "are you sure?" prompt hanging around for whichever row is expanded next.
    setCancellingId(null)
    setCancelError('')
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

  async function handleCancel(requestId) {
    setCancelSubmitting(true)
    setCancelError('')
    try {
      const updated = await cancelRequest(token, requestId)
      setRequests((prev) => prev.map((r) => (r.request_id === requestId ? updated : r)))
      setCancellingId(null)
    } catch (err) {
      setCancelError(err.message || 'Failed to cancel request')
    } finally {
      setCancelSubmitting(false)
    }
  }

  const statusCounts = {
    open: summary.by_status?.open || 0,
    'in-progress': summary.by_status?.['in-progress'] || 0,
    approved: summary.by_status?.approved || 0,
    rejected: summary.by_status?.rejected || 0,
  }

  return (
    <div>
      <PageHeader title="My requests" subtitle="Everything you've submitted, in one place." />

      <div className="mt-6">
        <Alert>{error}</Alert>
        {targetNotFound && (
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            Request #{targetRequestId} was not found in your requests.
          </div>
        )}
        {loading ? (
          <Spinner />
        ) : summary.total === 0 ? (
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
            <div className="mb-2 flex items-center justify-end">
              <FilterDropdown value={statusFilter} options={['all', ...STATUSES]} onChange={setStatusFilter} />
            </div>
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Description</th>
                  <SortableColumnHeader
                    label="Priority"
                    column="priority"
                    activeColumn={activeColumn}
                    direction={direction}
                    onToggle={toggleColumn}
                  />
                  <th className="px-4 py-3">Status</th>
                  <SortableColumnHeader
                    label="Created"
                    column="created"
                    activeColumn={activeColumn}
                    direction={direction}
                    onToggle={toggleColumn}
                  />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {requests.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      No requests with this status.
                    </td>
                  </tr>
                )}
                {requests.map((r) => {
                  const expanded = expandedId === r.request_id
                  const isDecided = DECIDED_STATUSES.includes(r.status)
                  const isCancelled = r.status === 'cancelled'
                  const isCancelling = cancellingId === r.request_id
                  return (
                    <Fragment key={r.request_id}>
                      <tr
                        ref={(el) => {
                          if (el) rowRefs.current[r.request_id] = el
                        }}
                        onClick={() => handleToggle(r)}
                        className={`cursor-pointer hover:bg-slate-50 ${isCancelled ? 'line-through' : ''}`}
                      >
                        <td className="px-4 py-3 text-slate-500">
                          <span className="flex items-center gap-2">
                            <ChevronIcon expanded={expanded} />#{r.request_id}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-900">{requestTypeLabel(r.request_type)}</td>
                        <td className="max-w-xs truncate px-4 py-3 text-slate-600">{r.description || '—'}</td>
                        <td className="px-4 py-3">
                          <PriorityBadge priority={r.priority} strikethrough={isCancelled} />
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={r.status} requestType={r.request_type} strikethrough={isCancelled} />
                        </td>
                        <td className="px-4 py-3 text-slate-500">{formatDateTime(r.created_at)}</td>
                      </tr>
                      {expanded && (
                        <tr className="bg-slate-50">
                          <td colSpan={6} className="px-4 py-4">
                            {!isDecided && !isCancelled && (
                              <div className="mb-3">
                                <SlaBadge priority={r.priority} createdAt={r.created_at} />
                              </div>
                            )}

                            {r.urgency_justification && (
                              <div className="mt-2 rounded-md bg-red-50 px-3 py-2 ring-1 ring-inset ring-red-200">
                                <p className="text-xs font-medium text-red-700">Why this was marked Urgent</p>
                                <p className="mt-0.5 text-sm text-red-700">{r.urgency_justification}</p>
                              </div>
                            )}

                            {isCancelled ? (
                              <p className="mt-3 text-sm text-slate-500">You cancelled this request.</p>
                            ) : !isDecided ? (
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

                            <div className="mt-4 border-t border-slate-200 pt-3">
                              <RequestComments
                                token={token}
                                requestId={r.request_id}
                                canAdd={!isCancelled}
                                currentUserId={user.user_id}
                                extraActions={
                                  CANCELLABLE_STATUSES.includes(r.status) && !isCancelling && (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setCancelError('')
                                        setCancellingId(r.request_id)
                                      }}
                                      className="cursor-pointer rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50"
                                    >
                                      Cancel Request
                                    </button>
                                  )
                                }
                              />
                              {isCancelling && (
                                <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-3">
                                  <p className="text-sm font-medium text-red-700">
                                    Are you sure you want to cancel this request?
                                  </p>
                                  <Alert>{cancelError}</Alert>
                                  <div className="mt-2 flex gap-2">
                                    <button
                                      type="button"
                                      onClick={() => handleCancel(r.request_id)}
                                      disabled={cancelSubmitting}
                                      className="cursor-pointer rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                      {cancelSubmitting ? 'Cancelling…' : 'Yes'}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setCancellingId(null)
                                        setCancelError('')
                                      }}
                                      disabled={cancelSubmitting}
                                      className="cursor-pointer rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                      No
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
            {total > 0 && (
              <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
            )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
