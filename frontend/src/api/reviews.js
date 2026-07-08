import { apiFetch } from './client'

export function getReviews(token) {
  return apiFetch('/reviews', { token })
}

export function createReview(token, { request_reference, decision, comment_text }) {
  return apiFetch('/reviews', {
    method: 'POST',
    token,
    body: { request_reference, decision, comment_text },
  })
}
