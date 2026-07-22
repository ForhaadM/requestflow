import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ReviewQueuePage } from './ReviewQueuePage'
import * as AuthContextModule from '../context/AuthContext'
import * as UsersContextModule from '../context/UsersContext'
import * as requestsApi from '../api/requests'

vi.mock('../context/AuthContext', async () => {
  const actual = await vi.importActual('../context/AuthContext')
  return { ...actual, useAuth: vi.fn() }
})
vi.mock('../context/UsersContext', async () => {
  const actual = await vi.importActual('../context/UsersContext')
  return { ...actual, useUsers: vi.fn() }
})
vi.mock('../api/requests')
vi.mock('../api/reviews', () => ({ createReview: vi.fn() }))

const REVIEWER = { user_id: 9, name: 'Riley Reviewer', role: 'reviewer' }

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

function nameFor(id) {
  return { 2: 'Rita Requester' }[id] || `user #${id}`
}
function emailFor(id) {
  return { 2: 'rita@example.com' }[id] || null
}

beforeEach(() => {
  vi.clearAllMocks()
  AuthContextModule.useAuth.mockReturnValue({ token: 'reviewer-token', user: REVIEWER })
  UsersContextModule.useUsers.mockReturnValue({ nameFor, emailFor })
  requestsApi.getAllRequests.mockResolvedValue([OPEN_REQUEST])
  requestsApi.getRequestComments.mockResolvedValue([])
})

describe('ReviewQueuePage', () => {
  it('shows the request ID on each queue row', async () => {
    render(<ReviewQueuePage />)
    await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument())
  })

  it('defaults to fetching only open/in-progress requests, matching the queue\'s previous behavior', async () => {
    render(<ReviewQueuePage />)
    await waitFor(() => {
      expect(requestsApi.getAllRequests).toHaveBeenCalledWith(
        'reviewer-token',
        expect.objectContaining({ status: ['open', 'in-progress'] })
      )
    })
  })

  it('re-fetches with the search term once the debounce settles', async () => {
    render(<ReviewQueuePage />)
    await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument())

    const searchBox = screen.getByPlaceholderText(/search by id/i)
    fireEvent.change(searchBox, { target: { value: 'monitor' } })

    await waitFor(
      () => {
        expect(requestsApi.getAllRequests).toHaveBeenCalledWith(
          'reviewer-token',
          expect.objectContaining({ search: 'monitor' })
        )
      },
      { timeout: 2000 }
    )
  })
})
