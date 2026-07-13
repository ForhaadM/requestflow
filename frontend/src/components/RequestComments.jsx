import { useEffect, useState } from 'react'
import { getRequestComments, addRequestComment } from '../api/requests'
import { CharCountTextarea } from './CharCountTextarea'
import { Spinner } from './Spinner'
import { Alert } from './Alert'
import { formatDateTime } from '../lib/formatDate'

// Must stay in sync with COMMENT_TEXT_MAX_LENGTH in backend/main.py.
const COMMENT_MAX_LENGTH = 750

// `resolveAuthorName(commenterReference)` is optional — omit it when the
// viewer can only ever see their own comments (e.g. a requester on their own
// request, who has no access to the user directory anyway), and every
// comment is labeled "You".
export function RequestComments({ token, requestId, canAdd, resolveAuthorName }) {
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    getRequestComments(token, requestId)
      .then(setComments)
      .catch((err) => setError(err.message || 'Failed to load comments'))
      .finally(() => setLoading(false))
  }, [token, requestId])

  async function handleAdd(e) {
    e.preventDefault()
    if (!text.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const comment = await addRequestComment(token, requestId, text.trim())
      setComments((prev) => [...prev, comment])
      setText('')
    } catch (err) {
      setError(err.message || 'Failed to add comment')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <p className="text-xs font-medium text-slate-500">Comments</p>

      {loading ? (
        <div className="mt-2"><Spinner label="Loading comments…" /></div>
      ) : comments.length === 0 ? (
        <p className="mt-1 text-sm text-slate-400">No comments yet.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {comments.map((c) => (
            <li key={c.comment_id} className="rounded-md border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-700">
                  {resolveAuthorName ? resolveAuthorName(c.commenter_reference) : 'You'}
                </span>
                <span className="text-xs text-slate-400">{formatDateTime(c.created_at)}</span>
              </div>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{c.comment_text}</p>
            </li>
          ))}
        </ul>
      )}

      <Alert>{error}</Alert>

      {canAdd && (
        <form onSubmit={handleAdd} className="mt-3">
          <CharCountTextarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={COMMENT_MAX_LENGTH}
            rows={2}
            placeholder="Add a comment…"
          />
          <button
            type="submit"
            disabled={submitting || !text.trim()}
            className="mt-2 cursor-pointer rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Adding…' : 'Add comment'}
          </button>
        </form>
      )}
    </div>
  )
}
