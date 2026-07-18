import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useUsers } from '../context/UsersContext'
import { getAllRequests, claimRequest, unclaimRequest } from '../api/requests'
import { createReview } from '../api/reviews'
import { PriorityBadge, SlaBadge } from '../components/Badge'
import { ClaimToggle } from '../components/ClaimToggle'
import { FadeSlide } from '../components/FadeSlide'
import { Spinner } from '../components/Spinner'
import { Alert } from '../components/Alert'
import { PageHeader } from '../components/PageHeader'
import { StatTile } from '../components/StatTile'
import { EmptyState } from '../components/EmptyState'
import { RequestDetailPanel } from '../components/RequestDetailPanel'
import { priorityRank } from '../lib/priority'
import { requestTypeLabel, decisionVerbsFor, requiresResolutionNotes } from '../lib/requestTypes'

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

function DecisionForm({ request, token, onReviewed }) {
  const verbs = decisionVerbsFor(request.request_type)
  const notesRequired = {
    APPROVED: requiresResolutionNotes(request.request_type),
    'NOT APPROVED': true,
  }

  const [pendingDecision, setPendingDecision] = useState(null)
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState('')

  async function submitDecision(decision, commentText) {
    setError('')
    if (notesRequired[decision] && !commentText.trim()) {
      setError(
        decision === 'APPROVED'
          ? 'A comment describing how this was resolved is required.'
          : 'A comment is required when rejecting a request.'
      )
      return
    }
    setSubmitting(decision)
    try {
      await createReview(token, {
        request_reference: request.request_id,
        decision,
        comment_text: commentText.trim() || null,
      })
      onReviewed(request.request_id, decision === 'APPROVED' ? 'approved' : 'rejected')
    } catch (err) {
      setError(err.message || 'Failed to submit review')
    } finally {
      setSubmitting('')
    }
  }

  function handleClickDecision(decision) {
    if (notesRequired[decision]) {
      setPendingDecision(decision)
      setError('')
    } else {
      submitDecision(decision, '')
    }
  }

  function handleCancel() {
    setPendingDecision(null)
    setComment('')
    setError('')
  }

  const notesLabel = pendingDecision === 'APPROVED' ? 'Resolution notes' : 'Comment'
  const notesPlaceholder =
    pendingDecision === 'APPROVED' ? 'Describe how this was resolved…' : 'Explain the reason…'

  return (
    <div className="mt-4">
      <div className="flex gap-2">
        <button
          onClick={() => handleClickDecision('APPROVED')}
          disabled={!!submitting || !!pendingDecision}
          className="cursor-pointer rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting === 'APPROVED' ? `${verbs.positiveAction}…` : verbs.positiveAction}
        </button>
        <button
          onClick={() => handleClickDecision('NOT APPROVED')}
          disabled={!!submitting || !!pendingDecision}
          className="cursor-pointer rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {verbs.negativeAction}
        </button>
      </div>

      <FadeSlide show={!!pendingDecision}>
        <div className="mt-3">
          <label className="block text-xs font-medium text-slate-700">
            {notesLabel} <span className="font-normal text-slate-400">(required)</span>
          </label>
          <textarea
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={notesPlaceholder}
            autoFocus
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />

          <Alert>{error}</Alert>

          <div className="mt-3 flex gap-2">
            <button
              onClick={() => submitDecision(pendingDecision, comment)}
              disabled={!!submitting}
              className="cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Submitting…' : 'Submit'}
            </button>
            <button
              onClick={handleCancel}
              disabled={!!submitting}
              className="cursor-pointer rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      </FadeSlide>
    </div>
  )
}

function QueueRow({ request, requesterName, requesterEmail, claimantName, currentUser, token, expanded, onToggleExpand, onClaimChanged, onReviewed }) {
  const [claiming, setClaiming] = useState(false)
  const [claimError, setClaimError] = useState('')

  const claimed = request.status === 'in-progress'
  const isMine = request.claimed_by === currentUser.user_id
  const isAdmin = currentUser.role === 'admin'
  const canToggle = claimed ? (isMine || isAdmin) : true
  const canDecide = claimed && (isMine || isAdmin)
  // Comments: the claiming reviewer or an admin, matching the backend's
  // create_comment_for_request authorization.
  const canAddComment = isAdmin || (claimed && isMine)

  async function handleToggleClaim() {
    setClaimError('')
    setClaiming(true)
    try {
      if (claimed) {
        const updated = await unclaimRequest(token, request.request_id)
        onClaimChanged(request.request_id, updated)
      } else {
        const updated = await claimRequest(token, request.request_id)
        onClaimChanged(request.request_id, updated)
      }
    } catch (err) {
      setClaimError(err.message || 'Failed to update claim')
    } finally {
      setClaiming(false)
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex w-full items-center gap-3 px-5 py-4">
        <button
          type="button"
          onClick={onToggleExpand}
          className="flex flex-1 cursor-pointer items-center gap-3 text-left"
        >
          <ChevronIcon expanded={expanded} />
          <span className="text-sm font-semibold text-slate-900">{requesterName}</span>
          <span className="text-sm text-slate-500">· {requestTypeLabel(request.request_type)}</span>
        </button>
        <PriorityBadge priority={request.priority} />
        <SlaBadge priority={request.priority} createdAt={request.created_at} />
        <ClaimToggle
          claimed={claimed}
          claimantName={claimantName}
          canToggle={canToggle}
          submitting={claiming}
          onToggle={handleToggleClaim}
        />
      </div>

      {claimError && <div className="px-5 pb-2"><Alert>{claimError}</Alert></div>}

      {expanded && (
        <div className="border-t border-slate-100 px-5 py-4">
          <RequestDetailPanel
            request={request}
            token={token}
            requesterEmail={requesterEmail}
            canAddComment={canAddComment}
            currentUserId={currentUser.user_id}
          />

          <FadeSlide show={canDecide}>
            <DecisionForm request={request} token={token} onReviewed={onReviewed} />
          </FadeSlide>
          <FadeSlide show={claimed && !canDecide}>
            <p className="mt-4 text-sm text-slate-500">
              Claimed by {claimantName} — waiting on their decision.
            </p>
          </FadeSlide>
        </div>
      )}
    </div>
  )
}

export function ReviewQueuePage() {
  const { token, user } = useAuth()
  const { nameFor, emailFor } = useUsers()
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const allRequests = await getAllRequests(token)
      setRequests(allRequests)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  // A request created through the chat widget (which stays mounted across
  // navigation, unlike the New Request form's own page) broadcasts this
  // event instead of this page having any other way to learn about it.
  useEffect(() => {
    window.addEventListener('requests:changed', load)
    return () => window.removeEventListener('requests:changed', load)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  function handleClaimChanged(requestId, updatedRequest) {
    setRequests((prev) => prev.map((r) => (r.request_id === requestId ? updatedRequest : r)))
  }

  function handleReviewed(requestId, newStatus) {
    setRequests((prev) =>
      prev.map((r) => (r.request_id === requestId ? { ...r, status: newStatus } : r))
    )
    setExpandedId(null)
  }

  const queue = requests
    .filter((r) => r.status === 'open' || r.status === 'in-progress')
    .sort((a, b) => priorityRank(a.priority) - priorityRank(b.priority))

  const openCount = useMemo(() => requests.filter((r) => r.status === 'open').length, [requests])
  const inProgressCount = useMemo(() => requests.filter((r) => r.status === 'in-progress').length, [requests])
  const mineCount = useMemo(
    () => requests.filter((r) => r.status === 'in-progress' && r.claimed_by === user.user_id).length,
    [requests, user.user_id]
  )

  return (
    <div>
      <PageHeader
        title="Review queue"
        subtitle="Claim a request to review it — only the claimant (or an admin) can approve or reject it."
      />

      {!loading && requests.length > 0 && (
        <div className="mt-6 grid grid-cols-3 gap-3">
          <StatTile label="Unclaimed" value={openCount} accent="text-blue-600" />
          <StatTile label="In Review" value={inProgressCount} accent="text-amber-600" />
          <StatTile label="Claimed by you" value={mineCount} accent="text-indigo-600" />
        </div>
      )}

      <div className="mt-6 space-y-3">
        <Alert>{error}</Alert>
        {loading ? (
          <Spinner />
        ) : queue.length === 0 ? (
          <EmptyState title="Nothing waiting for review right now." />
        ) : (
          queue.map((r) => (
            <QueueRow
              key={r.request_id}
              request={r}
              requesterName={nameFor(r.requester_reference)}
              requesterEmail={emailFor(r.requester_reference)}
              claimantName={r.claimed_by ? nameFor(r.claimed_by) : null}
              currentUser={user}
              token={token}
              expanded={expandedId === r.request_id}
              onToggleExpand={() => setExpandedId(expandedId === r.request_id ? null : r.request_id)}
              onClaimChanged={handleClaimChanged}
              onReviewed={handleReviewed}
            />
          ))
        )}
      </div>
    </div>
  )
}
