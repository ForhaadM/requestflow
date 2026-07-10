import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { createRequest } from '../api/requests'
import { Alert } from '../components/Alert'
import { CharCountTextarea } from '../components/CharCountTextarea'
import { InfoTooltip } from '../components/InfoTooltip'
import { PageHeader } from '../components/PageHeader'
import { PRIORITY_ORDER, PRIORITY_LABELS } from '../lib/priority'
import { REQUEST_TYPES } from '../lib/requestTypes'

const DESCRIPTION_MAX = 500
const JUSTIFICATION_MAX = 300

export function NewRequestPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    request_type: REQUEST_TYPES[0].value,
    description: '',
    priority: 'P1',
    urgency_justification: '',
  })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isUrgent = form.priority === 'P0'

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (!form.description.trim()) {
      setError('A description is required.')
      return
    }

    if (isUrgent && !form.urgency_justification.trim()) {
      setError('Please explain why this request is Urgent.')
      return
    }

    setSubmitting(true)
    try {
      await createRequest(token, {
        ...form,
        urgency_justification: isUrgent ? form.urgency_justification : null,
      })
      setSuccess('Request submitted.')
      setForm({ request_type: REQUEST_TYPES[0].value, description: '', priority: 'P1', urgency_justification: '' })
      setTimeout(() => navigate('/requests/mine'), 800)
    } catch (err) {
      setError(err.message || 'Failed to submit request')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title="Create a New Request" subtitle="Fill out the details below." />

      <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
            Request type
            <InfoTooltip
              title={REQUEST_TYPES.find((t) => t.value === form.request_type)?.label}
              items={REQUEST_TYPES.find((t) => t.value === form.request_type)?.examples || []}
            />
          </label>
          <select
            value={form.request_type}
            onChange={update('request_type')}
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {REQUEST_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Priority</label>
          <select
            value={form.priority}
            onChange={update('priority')}
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {PRIORITY_ORDER.map((p) => (
              <option key={p} value={p}>{PRIORITY_LABELS[p]}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">
            Description <span className="font-normal text-slate-400">(required)</span>
          </label>
          <div className="mt-1">
            <CharCountTextarea
              value={form.description}
              onChange={update('description')}
              maxLength={DESCRIPTION_MAX}
              rows={4}
              placeholder="Describe what you need…"
            />
          </div>
        </div>

        {isUrgent && (
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Why is this Urgent? <span className="font-normal text-slate-400">(required)</span>
            </label>
            <p className="mt-1 text-xs text-slate-500">
              Urgent requests jump to the top of the review queue — help reviewers understand why this
              can't wait.
            </p>
            <div className="mt-2">
              <CharCountTextarea
                value={form.urgency_justification}
                onChange={update('urgency_justification')}
                maxLength={JUSTIFICATION_MAX}
                rows={3}
                placeholder="Explain the impact and why it can't wait…"
                autoFocus
              />
            </div>
          </div>
        )}

        <Alert>{error}</Alert>
        <Alert type="success">{success}</Alert>

        <button
          type="submit"
          disabled={submitting}
          className="w-full cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? 'Submitting…' : 'Submit request'}
        </button>
      </form>
    </div>
  )
}
