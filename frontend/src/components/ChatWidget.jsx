import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { sendChatMessage } from '../api/chat'
import { ApiError } from '../api/client'

const QUICK_OPTIONS = [
  { label: 'Create a new request', message: 'I want to create a new request.', intent: 'create_request_menu' },
  { label: 'Check on a request', message: "What's the status of my requests?" },
  { label: 'What can I submit?', message: 'What request types can I submit?' },
]

function QuickOptionsPrompt({ userName, sending, onSelect }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-700">Hello {userName}, what do you need help with today?</p>
      <div className="flex flex-col gap-2">
        {QUICK_OPTIONS.map((option) => (
          <button
            key={option.label}
            type="button"
            onClick={() => onSelect(option.message, option.intent)}
            disabled={sending}
            className="cursor-pointer rounded-md border border-indigo-200 bg-indigo-50/50 px-3 py-2 text-left text-sm text-indigo-700 hover:border-indigo-300 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ChatWidget() {
  const { token, user, justLoggedIn, clearJustLoggedIn } = useAuth()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  // Shown at the start of a conversation, and again whenever the server says
  // the last reply was a dead end on its own (e.g. the "what can I submit?"
  // informational listing) — see show_quick_options on the /chat response.
  const [showQuickOptions, setShowQuickOptions] = useState(true)
  // True for the duration of the guided "Create a new request" flow (type
  // selection through urgency/justification/duplicate confirmation). Sent
  // with every /chat request so the server can deterministically recognize
  // a cancel-intent message at any step, and set from the server's response
  // each turn (it's the source of truth — the flow can start or end from the
  // model's own tool calls, not just client-side clicks). Also drives the
  // persistent "Cancel request" bar below.
  const [inCreationFlow, setInCreationFlow] = useState(false)
  const scrollRef = useRef(null)
  const panelRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, open, sending])

  // Auto-open once per login (not on every navigation/reload) so new users
  // notice the assistant exists. The flag is consumed immediately, so closing
  // the widget afterward doesn't cause it to reopen for the rest of the session.
  useEffect(() => {
    if (justLoggedIn) {
      setOpen(true)
      clearJustLoggedIn()
    }
  }, [justLoggedIn, clearJustLoggedIn])

  // Click-outside-to-close: only listens while the panel is open, and skips
  // the bubble button's own click so opening isn't immediately undone.
  useEffect(() => {
    if (!open) return

    function handleClickOutside(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  async function sendMessage(text, intent) {
    if (!text || sending) return

    const history = messages.map(({ role, content }) => ({ role, content }))
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setSending(true)
    setShowQuickOptions(false)

    try {
      const { reply, request_created, show_quick_options, in_creation_flow } = await sendChatMessage(
        token,
        text,
        history,
        intent,
        inCreationFlow,
      )
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }])
      setShowQuickOptions(!!show_quick_options)
      // The server is the source of truth for this — the guided flow can be
      // started or ended by the model itself (e.g. it decides to show the
      // type menu after "yes, create one"), not just by client-side clicks.
      setInCreationFlow(!!in_creation_flow)
      // Any request list already on screen (My Requests, Review Queue, the
      // admin dashboard, ...) fetched once on mount and has no way to know
      // about a request created through this always-mounted widget —
      // broadcast it the same way apiFetch already broadcasts auth:unauthorized.
      if (request_created) {
        window.dispatchEvent(new CustomEvent('requests:changed'))
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'
      setMessages((prev) => [...prev, { role: 'assistant', content: message, isError: true }])
    } finally {
      setSending(false)
    }
  }

  function handleSend(e) {
    e.preventDefault()
    sendMessage(input.trim())
  }

  function handleCancelFlow() {
    // Sent as a real message (not faked client-side) so the deterministic
    // cancel-intent check in the backend runs and the confirmation text
    // + main menu state come back through the normal response path.
    sendMessage('cancel')
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 cursor-pointer items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg transition-colors hover:bg-indigo-700"
        aria-label="Open Flowy Assistant"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-6 w-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h4m8-2a8 8 0 11-16 0 8 8 0 0116 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 20l-2-3.5a8 8 0 004-.5" />
        </svg>
      </button>
    )
  }

  return (
    <div
      ref={panelRef}
      className="fixed bottom-6 right-6 z-50 flex h-[32rem] w-96 max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl"
    >
      <div className="flex items-center justify-between border-b border-slate-200 bg-indigo-600 px-4 py-3">
        <span className="text-sm font-semibold text-white">Flowy Assistant</span>
        <button
          onClick={() => setOpen(false)}
          className="cursor-pointer rounded-md p-1 text-indigo-100 hover:bg-indigo-700 hover:text-white"
          aria-label="Collapse chat"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-4 py-3">
        {messages.length === 0 && showQuickOptions && (
          <QuickOptionsPrompt userName={user?.name?.split(' ')[0] || 'there'} sending={sending} onSelect={sendMessage} />
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : m.isError
                  ? 'bg-red-50 text-red-700 border border-red-200'
                  : 'bg-white text-slate-800 border border-slate-200'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {messages.length > 0 && showQuickOptions && !sending && (
          <QuickOptionsPrompt userName={user?.name?.split(' ')[0] || 'there'} sending={sending} onSelect={sendMessage} />
        )}
        {sending && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-2">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
            </div>
          </div>
        )}
      </div>

      {inCreationFlow && (
        <div className="border-t border-slate-200 bg-white px-4 py-2">
          <button
            type="button"
            onClick={handleCancelFlow}
            disabled={sending}
            className="cursor-pointer text-sm text-slate-500 underline decoration-dotted hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel request
          </button>
        </div>
      )}

      <form onSubmit={handleSend} className="flex items-center gap-2 border-t border-slate-200 bg-white p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={sending}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none disabled:bg-slate-100"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="cursor-pointer rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Send
        </button>
      </form>
    </div>
  )
}
