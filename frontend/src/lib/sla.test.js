import { describe, it, expect } from 'vitest'
import { getSlaStatus, formatSlaRemaining, formatSlaOutcome } from './sla'

describe('getSlaStatus', () => {
  it('is "ok" well within the window', () => {
    const now = new Date('2026-01-01T04:00:00Z')
    const createdAt = new Date('2026-01-01T00:00:00Z') // P1 window is 12h, 8h remaining here
    const { status } = getSlaStatus('P1', createdAt, now)
    expect(status).toBe('ok')
  })

  it('is "warning" once 25% or less of the window remains', () => {
    const createdAt = new Date('2026-01-01T00:00:00Z')
    const now = new Date('2026-01-01T09:30:00Z') // 2.5h left of a 12h window
    const { status } = getSlaStatus('P1', createdAt, now)
    expect(status).toBe('warning')
  })

  it('is "breached" once the deadline has passed', () => {
    const createdAt = new Date('2026-01-01T00:00:00Z')
    const now = new Date('2026-01-01T13:00:00Z') // past the 12h window
    const { status, remainingMs } = getSlaStatus('P1', createdAt, now)
    expect(status).toBe('breached')
    expect(remainingMs).toBeLessThan(0)
  })

  it('treats a bare backend timestamp (no Z/offset) as UTC, not local time', () => {
    // The backend always sends naive-but-actually-UTC timestamps, e.g.
    // "2026-01-01T00:00:00" with no trailing Z. Passing that raw string
    // (as the real Requests API response does) must be interpreted as UTC.
    const createdAt = '2026-01-01T00:00:00'
    const now = new Date('2026-01-01T01:00:00Z') // 1h after the true UTC instant
    const { remainingMs } = getSlaStatus('P1', createdAt, now) // P1 window is 12h
    // 1h elapsed out of a 12h window -> ~11h remaining, regardless of the
    // test runner's local timezone.
    expect(remainingMs).toBeCloseTo(11 * 60 * 60 * 1000, -3)
  })
})

describe('formatSlaOutcome', () => {
  it('reports a met SLA for a non-negative remaining time', () => {
    expect(formatSlaOutcome(30 * 60 * 1000)).toBe('Met SLA')
  })

  it('reports a missed SLA with the overage for a negative remaining time', () => {
    expect(formatSlaOutcome(-2 * 60 * 60 * 1000)).toBe('Missed SLA by 2h')
  })
})

describe('formatSlaRemaining', () => {
  it('reports remaining time when on track', () => {
    expect(formatSlaRemaining({ remainingMs: 2 * 60 * 60 * 1000, status: 'ok' })).toBe('2h left')
  })

  it('reports overage when breached', () => {
    expect(formatSlaRemaining({ remainingMs: -60 * 60 * 1000, status: 'breached' })).toBe('Breached by 1h')
  })
})
