import { apiFetch } from './client'

export function getMyRequests(token) {
  return apiFetch('/requests/me', { token })
}

// Admin and reviewer only (enforced server-side). `params` may include
// `search` (string) and `status`/`priority`/`request_type` (arrays) — all
// applied server-side so this scales the same way regardless of list size.
export function getAllRequests(token, params = {}) {
  const query = new URLSearchParams()
  const { search, status, priority, request_type } = params
  if (search && search.trim()) query.set('search', search.trim())
  for (const s of status || []) query.append('status', s)
  for (const p of priority || []) query.append('priority', p)
  for (const t of request_type || []) query.append('request_type', t)
  const qs = query.toString()
  return apiFetch(`/requests${qs ? `?${qs}` : ''}`, { token })
}

export function createRequest(token, { request_type, description, priority, urgency_justification }) {
  return apiFetch('/requests', {
    method: 'POST',
    token,
    body: { request_type, description, priority, urgency_justification },
  })
}

export function checkSimilarRequests(token, { request_type, description }) {
  return apiFetch('/requests/check-similar', {
    method: 'POST',
    token,
    body: { request_type, description },
  })
}

export function claimRequest(token, requestId) {
  return apiFetch(`/requests/${requestId}/claim`, { method: 'PATCH', token })
}

export function unclaimRequest(token, requestId) {
  return apiFetch(`/requests/${requestId}/unclaim`, { method: 'PATCH', token })
}

export function cancelRequest(token, requestId) {
  return apiFetch(`/requests/${requestId}/cancel`, { method: 'PATCH', token })
}

export function getRequestReviews(token, requestId) {
  return apiFetch(`/requests/${requestId}/reviews`, { token })
}

export function getRequestComments(token, requestId) {
  return apiFetch(`/requests/${requestId}/comments`, { token })
}

export function addRequestComment(token, requestId, commentText) {
  return apiFetch(`/requests/${requestId}/comments`, {
    method: 'POST',
    token,
    body: { comment_text: commentText },
  })
}
