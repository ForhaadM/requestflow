import { apiFetch } from './client'

export function registerUser({ name, email, password, role }) {
  return apiFetch('/users', { method: 'POST', body: { name, email, password, role } })
}

export function login({ email, password }) {
  return apiFetch('/login', { method: 'POST', body: { email, password } })
}

// Reviewer/admin only (enforced server-side) — the full user directory, used
// to label requesters/claimants by name. Regular users should use
// getCurrentUser instead, which only needs their own token.
export function getUsers(token) {
  return apiFetch('/users', { token })
}

export function getCurrentUser(token) {
  return apiFetch('/users/me', { token })
}
