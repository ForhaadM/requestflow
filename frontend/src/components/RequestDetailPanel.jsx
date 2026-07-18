import { useState } from 'react'
import { SlaBadge } from './Badge'
import { RequestComments } from './RequestComments'
import { formatDateTime } from '../lib/formatDate'

function CopyIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  )
}

function RequesterEmail({ email }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(email)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can be denied (permissions, insecure context, etc.)
      // — fail silently rather than throwing, since there's no useful
      // recovery action for the user here beyond just selecting the text.
    }
  }

  return (
    <div className="flex items-center gap-2 text-sm text-slate-600">
      <span>{email}</span>
      <button
        type="button"
        onClick={handleCopy}
        aria-label="Copy requester email"
        className="cursor-pointer rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
      >
        <CopyIcon />
      </button>
      <span className={`text-xs text-emerald-600 transition-opacity duration-150 ${copied ? 'opacity-100' : 'opacity-0'}`}>
        Email copied
      </span>
    </div>
  )
}

// Shared "full detail" view for a request — used by both the review queue
// (open/in-progress tickets) and completed reviews, so both show identical
// detail instead of the queue getting richer info than the completed view.
export function RequestDetailPanel({ request, token, requesterEmail, canAddComment, resolvedAt, currentUserId }) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">Submitted {formatDateTime(request.created_at)}</p>
        <SlaBadge priority={request.priority} createdAt={request.created_at} resolvedAt={resolvedAt} />
      </div>

      {requesterEmail && (
        <div className="mt-2">
          <RequesterEmail email={requesterEmail} />
        </div>
      )}

      <p className="mt-3 text-xs font-medium text-slate-500">Request Description:</p>
      <p className="mt-1 text-sm text-slate-600">{request.description || 'No description provided.'}</p>

      {request.urgency_justification && (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 ring-1 ring-inset ring-red-200">
          <p className="text-xs font-medium text-red-700">Why this is Urgent</p>
          <p className="mt-0.5 text-sm text-red-700">{request.urgency_justification}</p>
        </div>
      )}

      <div className="mt-4 border-t border-slate-200 pt-3">
        <RequestComments
          token={token}
          requestId={request.request_id}
          canAdd={canAddComment}
          currentUserId={currentUserId}
        />
      </div>
    </div>
  )
}
