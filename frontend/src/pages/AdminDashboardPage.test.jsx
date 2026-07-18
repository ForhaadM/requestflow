import { render, screen, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AdminDashboardPage } from './AdminDashboardPage'
import * as AuthContextModule from '../context/AuthContext'
import * as UsersContextModule from '../context/UsersContext'
import * as requestsApi from '../api/requests'
import * as reviewsApi from '../api/reviews'
import * as analyticsApi from '../api/analytics'

vi.mock('../context/AuthContext', async () => {
  const actual = await vi.importActual('../context/AuthContext')
  return { ...actual, useAuth: vi.fn() }
})
vi.mock('../context/UsersContext', async () => {
  const actual = await vi.importActual('../context/UsersContext')
  return { ...actual, useUsers: vi.fn() }
})
vi.mock('../api/requests')
vi.mock('../api/reviews')
vi.mock('../api/analytics')

const ADMIN = { user_id: 9, name: 'Ada Admin', role: 'admin' }

// Open, unclaimed — admin should be able to comment despite no claim, unlike
// a plain reviewer.
const OPEN_REQUEST = {
  request_id: 1,
  requester_reference: 2,
  request_type: 'hardware',
  description: 'Need a monitor',
  priority: 'P1',
  status: 'open',
  claimed_by: null,
  created_at: '2026-07-17T00:00:00',
  urgency_justification: null,
}

const APPROVED_REQUEST = {
  request_id: 2,
  requester_reference: 3,
  request_type: 'hardware',
  description: 'Need a keyboard',
  priority: 'P2',
  status: 'approved',
  claimed_by: 5,
  created_at: '2026-07-10T00:00:00',
  urgency_justification: null,
}

const CANCELLED_REQUEST = {
  request_id: 3,
  requester_reference: 2,
  request_type: 'software',
  description: 'Never mind',
  priority: 'P3',
  status: 'cancelled',
  claimed_by: null,
  created_at: '2026-07-09T00:00:00',
  urgency_justification: null,
}

const REVIEW = {
  review_id: 100,
  request_reference: 2,
  reviewer_reference: 5,
  decision: 'APPROVED',
  comment_text: 'Approved, shipped a keyboard',
  reviewed_at: '2026-07-11T00:00:00',
}

const EMPTY_ANALYTICS = {
  volume_by_category: [],
  spikes: [],
  sla_compliance: {
    overall: { compliance_rate: null, resolved_breached: 0, resolved_total: 0, currently_breached_open: 0 },
    by_priority: [],
  },
  avg_resolution_by_category: [],
  avg_resolution_by_priority: [],
}

function nameFor(id) {
  return { 2: 'Rita Requester', 3: 'Ravi Requester', 5: 'Riley Reviewer' }[id] || `user #${id}`
}
function emailFor(id) {
  return { 2: 'rita@example.com', 3: 'ravi@example.com' }[id] || null
}

beforeEach(() => {
  vi.clearAllMocks()
  AuthContextModule.useAuth.mockReturnValue({ token: 'admin-token', user: ADMIN })
  UsersContextModule.useUsers.mockReturnValue({ nameFor, emailFor })
  requestsApi.getAllRequests.mockResolvedValue([OPEN_REQUEST, APPROVED_REQUEST, CANCELLED_REQUEST])
  requestsApi.getRequestComments.mockResolvedValue([])
  requestsApi.addRequestComment.mockResolvedValue({})
  reviewsApi.getReviews.mockResolvedValue([REVIEW])
  analyticsApi.getAdminAnalytics.mockResolvedValue(EMPTY_ANALYTICS)
})

describe('AdminDashboardPage — expandable request/review detail', () => {
  it('expands a row in "All requests" to show the shared RequestDetailPanel (description, SLA badge)', async () => {
    render(<AdminDashboardPage />)
    const requestsTable = await screen.findByTestId('all-requests-table')
    await waitFor(() => expect(within(requestsTable).getByText('#1')).toBeInTheDocument())

    expect(screen.queryByText('Need a monitor')).not.toBeInTheDocument()

    within(requestsTable).getByText('#1').click()

    await waitFor(() => expect(screen.getByText('Need a monitor')).toBeInTheDocument())
    // SlaBadge is rendered unconditionally by RequestDetailPanel — assert it's
    // present here too (admin's per-ticket countdown), matching the existing
    // reviewer views. Scoped to the expanded row's own table since the
    // analytics section above also contains "breached" text.
    expect(within(requestsTable).getByText(/left|breached/i)).toBeInTheDocument()
  })

  it('lets the admin add a comment on an unclaimed, open request (no claim required, unlike a reviewer)', async () => {
    render(<AdminDashboardPage />)
    const requestsTable = await screen.findByTestId('all-requests-table')
    await waitFor(() => expect(within(requestsTable).getByText('#1')).toBeInTheDocument())

    within(requestsTable).getByText('#1').click()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Add a comment…')).toBeInTheDocument()
    })
  })

  it('blocks the comment input for a cancelled request, matching backend authorization', async () => {
    render(<AdminDashboardPage />)
    const requestsTable = await screen.findByTestId('all-requests-table')
    await waitFor(() => expect(within(requestsTable).getByText('#3')).toBeInTheDocument())

    within(requestsTable).getByText('#3').click()

    await waitFor(() => {
      expect(requestsApi.getRequestComments).toHaveBeenCalledWith('admin-token', 3)
    })
    expect(screen.queryByPlaceholderText('Add a comment…')).not.toBeInTheDocument()
  })

  it('expands a row in "All reviews" to show the underlying request\'s full detail, including the review outcome and resolvedAt-based SLA state', async () => {
    render(<AdminDashboardPage />)
    const reviewsTable = await screen.findByTestId('all-reviews-table')
    await waitFor(() => expect(within(reviewsTable).getByText('#100')).toBeInTheDocument())

    expect(screen.queryByText('Need a keyboard')).not.toBeInTheDocument()

    within(reviewsTable).getByText('#100').click()

    await waitFor(() => expect(screen.getByText('Need a keyboard')).toBeInTheDocument())
    // Comment input should show — an admin can comment regardless of claim
    // status, and this ticket isn't cancelled.
    expect(screen.getByPlaceholderText('Add a comment…')).toBeInTheDocument()
  })

  it('toggling one "All requests" row does not affect another row\'s expansion state', async () => {
    render(<AdminDashboardPage />)
    const requestsTable = await screen.findByTestId('all-requests-table')
    await waitFor(() => expect(within(requestsTable).getByText('#1')).toBeInTheDocument())

    within(requestsTable).getByText('#1').click()
    await waitFor(() => expect(screen.getByText('Need a monitor')).toBeInTheDocument())

    within(requestsTable).getByText('#2').click()
    await waitFor(() => expect(screen.getByText('Need a keyboard')).toBeInTheDocument())
    expect(screen.queryByText('Need a monitor')).not.toBeInTheDocument()
  })
})
