import { apiFetch } from './client'

export function registerUser({ name, email, password, role }) {
  return apiFetch('/users', { method: 'POST', body: { name, email, password, role } })
}

export function login({ email, password }) {
  return apiFetch('/login', { method: 'POST', body: { email, password } })
}

export function getUsers() {
  return apiFetch('/users')
}
