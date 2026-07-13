import { useEffect, useState } from 'react'
import { getAdminAnalytics } from '../api/analytics'
import { BarChart } from './BarChart'
import { Spinner } from './Spinner'
import { Alert } from './Alert'
import { requestTypeLabel } from '../lib/requestTypes'
import { PRIORITY_LABELS } from '../lib/priority'

const TREND_ARROW = { up: '↑', down: '↓', flat: '→' }
const VOLUME_BAR_COLOR = '#4f46e5'
const RESOLUTION_BAR_COLOR = '#0891b2'

export function AdminAnalyticsSection({ token }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getAdminAnalytics(token)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return <Spinner label="Loading patterns…" />
  if (error) return <Alert>{error}</Alert>
  if (!data) return null

  const volumeData = data.volume_by_category
    .filter((c) => c.total_30d > 0)
    .sort((a, b) => b.total_30d - a.total_30d)
    .map((c) => ({
      label: `${requestTypeLabel(c.request_type)}  ${TREND_ARROW[c.trend]}`,
      value: c.total_30d,
      color: VOLUME_BAR_COLOR,
    }))

  const resolutionByCategory = data.avg_resolution_by_category
    .filter((c) => c.resolved_count > 0)
    .sort((a, b) => b.avg_days - a.avg_days)
    .map((c) => ({
      label: requestTypeLabel(c.request_type),
      value: c.avg_days,
      color: RESOLUTION_BAR_COLOR,
    }))

  const resolutionByPriority = data.avg_resolution_by_priority
    .filter((p) => p.resolved_count > 0)
    .map((p) => ({
      label: PRIORITY_LABELS[p.priority] || p.priority,
      value: p.avg_days,
      color: RESOLUTION_BAR_COLOR,
    }))

  return (
    <section className="space-y-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Patterns (last 30 days)</h2>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700">Volume by category</h3>
          <p className="mt-1 text-xs text-slate-400">
            ↑/↓/→ compares the last 15 days to the 15 days before that.
          </p>
          <div className="mt-4">
            {volumeData.length > 0 ? (
              <BarChart ariaLabel="Volume by category, last 30 days" data={volumeData} />
            ) : (
              <p className="text-sm text-slate-400">No requests in the last 30 days.</p>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700">Unusual activity</h3>
          <p className="mt-1 text-xs text-slate-400">
            Categories where the last 7 days are running well above their recent average.
          </p>
          <div className="mt-4">
            {data.spikes.length === 0 ? (
              <p className="text-sm text-slate-400">No unusual spikes detected.</p>
            ) : (
              <ul className="space-y-2">
                {data.spikes.map((s) => (
                  <li
                    key={s.request_type}
                    className="flex items-center justify-between rounded-md bg-red-50 px-3 py-2 text-sm ring-1 ring-inset ring-red-200"
                  >
                    <span className="font-medium text-red-700">⚠ {requestTypeLabel(s.request_type)}</span>
                    <span className="text-red-600">
                      {s.recent_count} in the last 7 days (~{s.expected_count} expected)
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700">SLA compliance</h3>
        <p className="mt-1 text-xs text-slate-400">
          Resolved requests are compared to their priority's SLA window ({PRIORITY_LABELS.P0}: 2h, {PRIORITY_LABELS.P1}: 12h,{' '}
          {PRIORITY_LABELS.P2}: 7d, {PRIORITY_LABELS.P3}: 14d) from creation.
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-lg bg-slate-50 p-3 ring-1 ring-inset ring-slate-200">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Overall</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {data.sla_compliance.overall.compliance_rate === null ? '—' : `${data.sla_compliance.overall.compliance_rate}%`}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              {data.sla_compliance.overall.resolved_breached} breached / {data.sla_compliance.overall.resolved_total} resolved
            </p>
            {data.sla_compliance.overall.currently_breached_open > 0 && (
              <p className="mt-1 text-xs font-medium text-red-600">
                {data.sla_compliance.overall.currently_breached_open} open past SLA now
              </p>
            )}
          </div>
          {data.sla_compliance.by_priority.map((p) => (
            <div key={p.priority} className="rounded-lg bg-slate-50 p-3 ring-1 ring-inset ring-slate-200">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {PRIORITY_LABELS[p.priority] || p.priority}
              </p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {p.compliance_rate === null ? '—' : `${p.compliance_rate}%`}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                {p.resolved_breached} breached / {p.resolved_total} resolved
              </p>
              {p.currently_breached_open > 0 && (
                <p className="mt-1 text-xs font-medium text-red-600">{p.currently_breached_open} open past SLA</p>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700">Avg. days to resolution by category</h3>
          <div className="mt-4">
            {resolutionByCategory.length > 0 ? (
              <BarChart ariaLabel="Average days to resolution by category" data={resolutionByCategory} />
            ) : (
              <p className="text-sm text-slate-400">Not enough decided requests yet.</p>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700">Avg. days to resolution by priority</h3>
          <div className="mt-4">
            {resolutionByPriority.length > 0 ? (
              <BarChart ariaLabel="Average days to resolution by priority" data={resolutionByPriority} />
            ) : (
              <p className="text-sm text-slate-400">Not enough decided requests yet.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
