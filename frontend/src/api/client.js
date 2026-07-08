const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

// Thin fetch wrapper: attaches the bearer token when present, throws
// ApiError with the backend's `detail` message on non-2xx responses so
// callers can show it directly in the UI.
export async function apiFetch(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const isJson = res.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await res.json() : null

  if (!res.ok) {
    const message = data?.detail || res.statusText || 'Request failed'
    // A 401 means the token is missing/expired/invalid — there's no page-level
    // recovery from that, so broadcast it once and let AuthContext handle the
    // sign-out + redirect centrally instead of every caller checking status.
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
    throw new ApiError(
      typeof message === 'string' ? message : JSON.stringify(message),
      res.status
    )
  }

  return data
}
