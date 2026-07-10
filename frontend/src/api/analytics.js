import { apiFetch } from './client'

export function getAdminAnalytics(token) {
  return apiFetch('/admin/analytics', { token })
}
