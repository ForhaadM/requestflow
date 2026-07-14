import { apiFetch } from './client'

export function sendChatMessage(token, message, history, intent, inCreationFlow) {
  return apiFetch('/chat', {
    method: 'POST',
    token,
    body: { message, history, intent, in_creation_flow: !!inCreationFlow },
  })
}
