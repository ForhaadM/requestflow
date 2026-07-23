import { apiFetch } from './client'

// Shared by both `/requests` and `/requests/me` — pagination/sort params are
// identical on both endpoints.
function appendPagingParams(query, { page, page_size, sort, sort_dir } = {}) {
  if (page) query.set('page', page)
  if (page_size) query.set('page_size', page_size)
  if (sort) query.set('sort', sort)
  if (sort_dir) query.set('sort_dir', sort_dir)
}

// Returns {items, total, page, page_size, total_pages} — the requester's own
// requests, paginated/sorted server-side.
export function getMyRequests(token, params = {}) {
  const query = new URLSearchParams()
  const { status } = params
  if (status && status !== 'all') query.set('status', status)
  appendPagingParams(query, params)
  const qs = query.toString()
  return apiFetch(`/requests/me${qs ? `?${qs}` : ''}`, { token })
}

export function getMyRequestsSummary(token) {
  return apiFetch('/requests/me/summary', { token })
}

// Admin and reviewer only (enforced server-side). `params` may include
// `search` (string), `status`/`priority`/`request_type` (arrays), and paging
// (`page`/`page_size`/`sort`/`sort_dir`) — all applied server-side so this
// scales the same way regardless of list size. Returns
// {items, total, page, page_size, total_pages}.
export function getAllRequests(token, params = {}) {
  const query = new URLSearchParams()
  const { search, status, priority, request_type } = params
  if (search && search.trim()) query.set('search', search.trim())
  for (const s of status || []) query.append('status', s)
  for (const p of priority || []) query.append('priority', p)
  for (const t of request_type || []) query.append('request_type', t)
  appendPagingParams(query, params)
  const qs = query.toString()
  return apiFetch(`/requests${qs ? `?${qs}` : ''}`, { token })
}

// Aggregate counts (by status/type, plus a total and how many are claimed by
// the caller) for the reviewer/admin "all requests" view — powers dashboard
// charts/stat tiles without needing a full-table fetch.
export function getRequestsSummary(token, params = {}) {
  const query = new URLSearchParams()
  const { search, priority, request_type } = params
  if (search && search.trim()) query.set('search', search.trim())
  for (const p of priority || []) query.append('priority', p)
  for (const t of request_type || []) query.append('request_type', t)
  const qs = query.toString()
  return apiFetch(`/requests/summary${qs ? `?${qs}` : ''}`, { token })
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
