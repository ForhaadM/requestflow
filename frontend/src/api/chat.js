import { apiFetch } from './client'

export function sendChatMessage(token, message, history) {
  return apiFetch('/chat', {
    method: 'POST',
    token,
    body: { message, history },
  })
}
