import { apiFetch } from './client'

export function getMyRequests(token) {
  return apiFetch('/requests/me', { token })
}

// Admin and reviewer only (enforced server-side).
export function getAllRequests(token) {
  return apiFetch('/requests', { token })
}

export function createRequest(token, { request_type, description, priority, urgency_justification }) {
  return apiFetch('/requests', {
    method: 'POST',
    token,
    body: { request_type, description, priority, urgency_justification },
  })
}

export function claimRequest(token, requestId) {
  return apiFetch(`/requests/${requestId}/claim`, { method: 'PATCH', token })
}

export function unclaimRequest(token, requestId) {
  return apiFetch(`/requests/${requestId}/unclaim`, { method: 'PATCH', token })
}

export function getRequestReviews(token, requestId) {
  return apiFetch(`/requests/${requestId}/reviews`, { token })
}
