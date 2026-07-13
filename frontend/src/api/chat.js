import { apiFetch } from './client'

export function sendChatMessage(token, message, history, intent) {
  return apiFetch('/chat', {
    method: 'POST',
    token,
    body: { message, history, intent },
  })
}
