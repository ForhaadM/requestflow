import { Fragment, useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useUsers } from '../context/UsersContext'
import { getAllRequests, getRequestsSummary } from '../api/requests'
import { getReviews, createReview } from '../api/reviews'
import { StatusBadge, PriorityBadge, DecisionBadge } from '../components/Badge'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { PageHeader } from '../components/PageHeader'
import { MultiSelectFilter } from '../components/MultiSelectFilter'
import { SearchInput } from '../components/SearchInput'
import { BarChart } from '../components/BarChart'
import { AdminAnalyticsSection } from '../components/AdminAnalyticsSection'
import { SortableColumnHeader } from '../components/SortableColumnHeader'
import { RequestDetailPanel } from '../components/RequestDetailPanel'
import { Pagination } from '../components/Pagination'
import { formatDateTime } from '../lib/formatDate'
import { REQUEST_TYPES, requestTypeLabel, decisionVerbsFor } from '../lib/requestTypes'
import { PRIORITY_ORDER, PRIORITY_LABELS } from '../lib/priority'
import { useColumnSort } from '../lib/useColumnSort'

const TABLE_PAGE_SIZE = 25
const REVIEWS_PAGE_SIZE = 25

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

// Includes "cancelled" (unlike STATUSES above, which is only for the
// by-status chart) since the "All requests" table's status filter should
// let an admin narrow to any status a request can actually be in.
const FILTER_STATUS_OPTIONS = ['open', 'in-progress', 'approved', 'rejected', 'cancelled']
const FILTER_STATUS_LABELS = { ...STATUS_LABELS, cancelled: 'Cancelled' }

// Single hue for every bar: type is nominal (position + label already carry
// identity), so color doesn't need to distinguish categories here.
const TYPE_BAR_COLOR = '#4f46e5'

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
  const { token, user } = useAuth()
  const { nameFor, emailFor } = useUsers()
  const [summary, setSummary] = useState({ total: 0, by_status: {}, by_type: {} })
  const [tableRequests, setTableRequests] = useState([])
  const [tableTotal, setTableTotal] = useState(0)
  const [tableTotalPages, setTableTotalPages] = useState(0)
  const [tablePage, setTablePage] = useState(1)
  const [reviews, setReviews] = useState([])
  const [reviewsTotal, setReviewsTotal] = useState(0)
  const [reviewsTotalPages, setReviewsTotalPages] = useState(0)
  const [reviewsPage, setReviewsPage] = useState(1)
  const [reviewsLoading, setReviewsLoading] = useState(true)
  const [loading, setLoading] = useState(true)
  const [tableLoading, setTableLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState([])
  const [priorityFilter, setPriorityFilter] = useState([])
  const [typeFilter, setTypeFilter] = useState([])
  const [overridingId, setOverridingId] = useState(null)
  const [expandedRequestId, setExpandedRequestId] = useState(null)
  const [expandedReviewId, setExpandedReviewId] = useState(null)

  const { activeColumn, direction, toggleColumn } = useColumnSort('created', ['priority', 'created'])

  // The charts and "Total requests" tile above always reflect the full,
  // unfiltered system — only the "All requests" table below is scoped by
  // search/filters, via `tableRequests`/loadTable.
  function load() {
    getRequestsSummary(token)
      .then(setSummary)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  function loadTable() {
    setTableLoading(true)
    getAllRequests(token, {
      search,
      status: statusFilter,
      priority: priorityFilter,
      request_type: typeFilter,
      page: tablePage,
      page_size: TABLE_PAGE_SIZE,
      sort: activeColumn,
      sort_dir: direction,
    })
      .then((response) => {
        setTableRequests(response.items)
        setTableTotal(response.total)
        setTableTotalPages(response.total_pages)
      })
      .catch((err) => setError(err.message))
      .finally(() => setTableLoading(false))
  }

  function loadReviews() {
    setReviewsLoading(true)
    getReviews(token, { page: reviewsPage, page_size: REVIEWS_PAGE_SIZE })
      .then((response) => {
        setReviews(response.items)
        setReviewsTotal(response.total)
        setReviewsTotalPages(response.total_pages)
      })
      .catch((err) => setError(err.message))
      .finally(() => setReviewsLoading(false))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    loadTable()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, search, statusFilter, priorityFilter, typeFilter, tablePage, activeColumn, direction])

  useEffect(() => {
    loadReviews()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, reviewsPage])

  // Changing a filter or sort column should show page 1 of the new result
  // set, not whatever page the previous view happened to be on.
  useEffect(() => {
    setTablePage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter, priorityFilter, typeFilter, activeColumn, direction])

  // A request created through the chat widget (which stays mounted across
  // navigation, unlike the New Request form's own page) broadcasts this
  // event instead of this page having any other way to learn about it.
  useEffect(() => {
    function handleChanged() {
      load()
      loadTable()
      loadReviews()
    }
    window.addEventListener('requests:changed', handleChanged)
    return () => window.removeEventListener('requests:changed', handleChanged)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, search, statusFilter, priorityFilter, typeFilter, tablePage, activeColumn, direction, reviewsPage])

  const byStatus = summary.by_status || {}
  const byType = summary.by_type || {}

  const visibleRequests = tableRequests

  function handleOverridden(requestId, review, newStatus) {
    setTableRequests((prev) =>
      prev.map((r) => (r.request_id === requestId ? { ...r, status: newStatus } : r))
    )
    // The override created a new review, so re-fetch the (paginated) reviews
    // list rather than appending locally — appending would desync from
    // `reviewsTotal`/`reviewsTotalPages`.
    loadReviews()
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
            <p className="text-5xl font-semibold tabular-nums text-white">{summary.total}</p>
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

      <AdminAnalyticsSection token={token} />

      <section>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">All requests</h2>
          <div className="flex flex-wrap items-center gap-2">
            <SearchInput value={search} onSearch={setSearch} placeholder="Search by ID, requester, or description…" />
            <MultiSelectFilter
              label="Status"
              value={statusFilter}
              options={FILTER_STATUS_OPTIONS}
              optionLabel={(s) => FILTER_STATUS_LABELS[s]}
              onChange={setStatusFilter}
            />
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
              options={TYPES}
              optionLabel={requestTypeLabel}
              onChange={setTypeFilter}
            />
          </div>
        </div>

        <div data-testid="all-requests-section" className="mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table data-testid="all-requests-table" className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Requester</th>
                <th className="px-4 py-3">Type</th>
                <SortableColumnHeader
                  label="Priority"
                  column="priority"
                  activeColumn={activeColumn}
                  direction={direction}
                  onToggle={toggleColumn}
                />
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Claimed By</th>
                <SortableColumnHeader
                  label="Created"
                  column="created"
                  activeColumn={activeColumn}
                  direction={direction}
                  onToggle={toggleColumn}
                />
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tableLoading && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    <Spinner />
                  </td>
                </tr>
              )}
              {!tableLoading && visibleRequests.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    No requests match your search and filters.
                  </td>
                </tr>
              )}
              {!tableLoading && visibleRequests.map((r) => {
                const expanded = expandedRequestId === r.request_id
                return (
                  <Fragment key={r.request_id}>
                    <tr
                      onClick={() => setExpandedRequestId(expanded ? null : r.request_id)}
                      className="cursor-pointer hover:bg-slate-50"
                    >
                      <td className="px-4 py-3 text-slate-500">
                        <span className="flex items-center gap-2">
                          <ChevronIcon expanded={expanded} />#{r.request_id}
                        </span>
                      </td>
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
                            onClick={(e) => {
                              e.stopPropagation()
                              setOverridingId(overridingId === r.request_id ? null : r.request_id)
                            }}
                            className="cursor-pointer text-sm font-medium text-indigo-600 hover:underline"
                          >
                            {r.status === 'rejected' ? 'Override rejection' : 'Reverse decision'}
                          </button>
                        )}
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="bg-slate-50">
                        <td colSpan={8} className="px-4 py-4">
                          <RequestDetailPanel
                            request={r}
                            token={token}
                            requesterEmail={emailFor(r.requester_reference)}
                            // This page is admin-only (see App.jsx), so an admin can
                            // comment on any ticket regardless of claim status,
                            // matching create_comment_for_request — only a cancelled
                            // request stays locked, for everyone including admins.
                            canAddComment={r.status !== 'cancelled'}
                            currentUserId={user.user_id}
                          />
                        </td>
                      </tr>
                    )}
                    {overridingId === r.request_id && (
                      <OverrideRow
                        request={r}
                        token={token}
                        onOverridden={handleOverridden}
                        onCancel={() => setOverridingId(null)}
                      />
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          {!tableLoading && tableTotal > 0 && (
            <Pagination
              page={tablePage}
              totalPages={tableTotalPages}
              total={tableTotal}
              pageSize={TABLE_PAGE_SIZE}
              onPageChange={setTablePage}
            />
          )}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">All reviews</h2>
        <div data-testid="all-reviews-section" className="mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table data-testid="all-reviews-table" className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Request</th>
                <th className="px-4 py-3">Reviewed By</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Comment</th>
                <th className="px-4 py-3">Reviewed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reviewsLoading && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    <Spinner />
                  </td>
                </tr>
              )}
              {!reviewsLoading && reviews.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    No reviews yet.
                  </td>
                </tr>
              )}
              {!reviewsLoading && reviews.map((rv) => {
                const expanded = expandedReviewId === rv.review_id
                const request = rv.request
                return (
                  <Fragment key={rv.review_id}>
                    <tr
                      onClick={() => setExpandedReviewId(expanded ? null : rv.review_id)}
                      className="cursor-pointer hover:bg-slate-50"
                    >
                      <td className="px-4 py-3 text-slate-500">
                        <span className="flex items-center gap-2">
                          <ChevronIcon expanded={expanded} />#{rv.review_id}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">#{rv.request_reference}</td>
                      <td className="px-4 py-3 text-slate-600">{nameFor(rv.reviewer_reference)}</td>
                      <td className="px-4 py-3">
                        <DecisionBadge decision={rv.decision} requestType={request.request_type} />
                      </td>
                      <td className="max-w-xs truncate px-4 py-3 text-slate-600">{rv.comment_text || '—'}</td>
                      <td className="px-4 py-3 text-slate-500">{formatDateTime(rv.reviewed_at)}</td>
                    </tr>
                    {expanded && (
                      <tr className="bg-slate-50">
                        <td colSpan={6} className="px-4 py-4">
                          <RequestDetailPanel
                            request={request}
                            token={token}
                            requesterEmail={emailFor(request.requester_reference)}
                            canAddComment={request.status !== 'cancelled'}
                            currentUserId={user.user_id}
                            resolvedAt={rv.reviewed_at}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          {!reviewsLoading && reviewsTotal > 0 && (
            <Pagination
              page={reviewsPage}
              totalPages={reviewsTotalPages}
              total={reviewsTotal}
              pageSize={REVIEWS_PAGE_SIZE}
              onPageChange={setReviewsPage}
            />
          )}
        </div>
      </section>
    </div>
  )
}
