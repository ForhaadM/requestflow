import { apiFetch } from './client'

// Admin sees every review, reviewer sees only their own, requester sees
// none (enforced server-side). `params` may include `search` (string),
// `priority`/`request_type` (arrays), `decision` ('APPROVED'|'NOT APPROVED'),
// and paging (`page`/`page_size`) — all applied server-side, composed with a
// join to the review's request so filtering/pagination reflect the same
// matching set. Returns {items, total, page, page_size, total_pages}; each
// item includes a nested `request` with the full associated request.
export function getReviews(token, params = {}) {
  const query = new URLSearchParams()
  const { search, priority, request_type, decision, page, page_size } = params
  if (search && search.trim()) query.set('search', search.trim())
  for (const p of priority || []) query.append('priority', p)
  for (const t of request_type || []) query.append('request_type', t)
  if (decision) query.set('decision', decision)
  if (page) query.set('page', page)
  if (page_size) query.set('page_size', page_size)
  const qs = query.toString()
  return apiFetch(`/reviews${qs ? `?${qs}` : ''}`, { token })
}

export function createReview(token, { request_reference, decision, comment_text }) {
  return apiFetch('/reviews', {
    method: 'POST',
    token,
    body: { request_reference, decision, comment_text },
  })
}
