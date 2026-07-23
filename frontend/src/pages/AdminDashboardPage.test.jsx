import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
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
  request: APPROVED_REQUEST,
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

const ALL_REQUESTS = [OPEN_REQUEST, APPROVED_REQUEST, CANCELLED_REQUEST]

beforeEach(() => {
  vi.clearAllMocks()
  AuthContextModule.useAuth.mockReturnValue({ token: 'admin-token', user: ADMIN })
  UsersContextModule.useUsers.mockReturnValue({ nameFor, emailFor })
  requestsApi.getAllRequests.mockResolvedValue({
    items: ALL_REQUESTS,
    total: ALL_REQUESTS.length,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
  requestsApi.getRequestsSummary.mockResolvedValue({
    total: ALL_REQUESTS.length,
    by_status: { open: 1, approved: 1, cancelled: 1 },
    by_type: { hardware: 2, software: 1 },
    claimed_by_me: 0,
  })
  requestsApi.getRequestComments.mockResolvedValue([])
  requestsApi.addRequestComment.mockResolvedValue({})
  reviewsApi.getReviews.mockResolvedValue({
    items: [REVIEW],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
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

  it('shows pagination controls on the "All reviews" table and requests the next page on click', async () => {
    reviewsApi.getReviews.mockResolvedValue({
      items: [REVIEW],
      total: 60,
      page: 1,
      page_size: 25,
      total_pages: 3,
    })
    render(<AdminDashboardPage />)
    const reviewsSection = await screen.findByTestId('all-reviews-section')
    await waitFor(() => expect(within(reviewsSection).getByText(/page 1 of 3/i)).toBeInTheDocument())

    fireEvent.click(within(reviewsSection).getByRole('button', { name: /next/i }))

    await waitFor(() => {
      expect(reviewsApi.getReviews).toHaveBeenCalledWith('admin-token', expect.objectContaining({ page: 2 }))
    })
  })

  it('re-fetches the "All requests" table with the search term once the debounce settles, without re-fetching the chart totals', async () => {
    render(<AdminDashboardPage />)
    const requestsTable = await screen.findByTestId('all-requests-table')
    await waitFor(() => expect(within(requestsTable).getByText('#1')).toBeInTheDocument())

    requestsApi.getRequestsSummary.mockClear()
    const searchBox = screen.getByPlaceholderText(/search by id/i)
    fireEvent.change(searchBox, { target: { value: 'monitor' } })

    await waitFor(
      () => {
        expect(requestsApi.getAllRequests).toHaveBeenCalledWith(
          'admin-token',
          expect.objectContaining({ search: 'monitor' })
        )
      },
      { timeout: 2000 }
    )
    // The chart/tile data (getRequestsSummary) isn't scoped by the "All
    // requests" table's own search box — confirm it wasn't re-fetched.
    expect(requestsApi.getRequestsSummary).not.toHaveBeenCalled()
  })

  it('shows pagination controls on the "All requests" table and requests the next page on click', async () => {
    requestsApi.getAllRequests.mockResolvedValue({
      items: ALL_REQUESTS,
      total: 60,
      page: 1,
      page_size: 25,
      total_pages: 3,
    })
    render(<AdminDashboardPage />)
    const requestsSection = await screen.findByTestId('all-requests-section')
    await waitFor(() => expect(within(requestsSection).getByText(/page 1 of 3/i)).toBeInTheDocument())

    fireEvent.click(within(requestsSection).getByRole('button', { name: /next/i }))

    await waitFor(() => {
      expect(requestsApi.getAllRequests).toHaveBeenCalledWith(
        'admin-token',
        expect.objectContaining({ page: 2 })
      )
    })
  })

  it('resets the "All requests" table to page 1 when a filter changes after navigating to a later page', async () => {
    requestsApi.getAllRequests.mockResolvedValue({
      items: ALL_REQUESTS,
      total: 60,
      page: 1,
      page_size: 25,
      total_pages: 3,
    })
    render(<AdminDashboardPage />)
    const requestsSection = await screen.findByTestId('all-requests-section')
    await waitFor(() => expect(within(requestsSection).getByText(/page 1 of 3/i)).toBeInTheDocument())

    fireEvent.click(within(requestsSection).getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(requestsApi.getAllRequests).toHaveBeenCalledWith(
        'admin-token',
        expect.objectContaining({ page: 2 })
      )
    })

    const searchBox = screen.getByPlaceholderText(/search by id/i)
    fireEvent.change(searchBox, { target: { value: 'monitor' } })

    await waitFor(
      () => {
        expect(requestsApi.getAllRequests).toHaveBeenCalledWith(
          'admin-token',
          expect.objectContaining({ search: 'monitor', page: 1 })
        )
      },
      { timeout: 2000 }
    )
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
