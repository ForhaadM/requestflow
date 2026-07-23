import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CompletedReviewsPage } from './CompletedReviewsPage'
import * as AuthContextModule from '../context/AuthContext'
import * as UsersContextModule from '../context/UsersContext'
import * as reviewsApi from '../api/reviews'

vi.mock('../context/AuthContext', async () => {
  const actual = await vi.importActual('../context/AuthContext')
  return { ...actual, useAuth: vi.fn() }
})
vi.mock('../context/UsersContext', async () => {
  const actual = await vi.importActual('../context/UsersContext')
  return { ...actual, useUsers: vi.fn() }
})
vi.mock('../api/reviews')

const REVIEWER = { user_id: 5, name: 'Riley Reviewer', role: 'reviewer' }

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

const REVIEW = {
  review_id: 100,
  request_reference: 2,
  reviewer_reference: 5,
  decision: 'APPROVED',
  comment_text: 'Approved, shipped a keyboard',
  reviewed_at: '2026-07-11T00:00:00',
  request: APPROVED_REQUEST,
}

function nameFor(id) {
  return { 3: 'Ravi Requester' }[id] || `user #${id}`
}
function emailFor(id) {
  return { 3: 'ravi@example.com' }[id] || null
}

beforeEach(() => {
  vi.clearAllMocks()
  AuthContextModule.useAuth.mockReturnValue({ token: 'reviewer-token', user: REVIEWER })
  UsersContextModule.useUsers.mockReturnValue({ nameFor, emailFor })
  reviewsApi.getReviews.mockResolvedValue({
    items: [REVIEW],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
})

describe('CompletedReviewsPage', () => {
  it('shows the request ID column', async () => {
    render(<CompletedReviewsPage />)
    await waitFor(() => expect(screen.getByText('#2')).toBeInTheDocument())
  })

  it('shows the empty state when GET /reviews returns nothing matching', async () => {
    reviewsApi.getReviews.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25, total_pages: 0 })
    render(<CompletedReviewsPage />)
    await waitFor(() => {
      expect(screen.getByText('No completed reviews yet.')).toBeInTheDocument()
    })
    expect(screen.queryByText('#2')).not.toBeInTheDocument()
  })

  it('re-fetches with the search term once the debounce settles', async () => {
    render(<CompletedReviewsPage />)
    await waitFor(() => expect(screen.getByText('#2')).toBeInTheDocument())

    const searchBox = screen.getByPlaceholderText(/search by id/i)
    fireEvent.change(searchBox, { target: { value: 'keyboard' } })

    await waitFor(
      () => {
        expect(reviewsApi.getReviews).toHaveBeenCalledWith(
          'reviewer-token',
          expect.objectContaining({ search: 'keyboard' })
        )
      },
      { timeout: 2000 }
    )
  })

  it('shows pagination controls and requests the next page on click', async () => {
    reviewsApi.getReviews.mockResolvedValue({
      items: [REVIEW],
      total: 60,
      page: 1,
      page_size: 25,
      total_pages: 3,
    })
    render(<CompletedReviewsPage />)
    await waitFor(() => expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    await waitFor(() => {
      expect(reviewsApi.getReviews).toHaveBeenCalledWith('reviewer-token', expect.objectContaining({ page: 2 }))
    })
  })

  it('resets to page 1 when a filter changes after navigating to a later page', async () => {
    reviewsApi.getReviews.mockResolvedValue({
      items: [REVIEW],
      total: 60,
      page: 1,
      page_size: 25,
      total_pages: 3,
    })
    render(<CompletedReviewsPage />)
    await waitFor(() => expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(reviewsApi.getReviews).toHaveBeenCalledWith('reviewer-token', expect.objectContaining({ page: 2 }))
    })

    const searchBox = screen.getByPlaceholderText(/search by id/i)
    fireEvent.change(searchBox, { target: { value: 'keyboard' } })

    await waitFor(
      () => {
        expect(reviewsApi.getReviews).toHaveBeenCalledWith(
          'reviewer-token',
          expect.objectContaining({ search: 'keyboard', page: 1 })
        )
      },
      { timeout: 2000 }
    )
  })

  it('passes the decision filter through to GET /reviews', async () => {
    render(<CompletedReviewsPage />)
    await waitFor(() => expect(screen.getByText('#2')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Decision: All'))
    fireEvent.click(screen.getByRole('button', { name: 'Approved' }))

    await waitFor(() => {
      expect(reviewsApi.getReviews).toHaveBeenCalledWith(
        'reviewer-token',
        expect.objectContaining({ decision: 'APPROVED' })
      )
    })
  })
})
