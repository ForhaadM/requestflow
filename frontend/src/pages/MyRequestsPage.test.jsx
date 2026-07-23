import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MyRequestsPage } from './MyRequestsPage'
import * as AuthContextModule from '../context/AuthContext'
import * as requestsApi from '../api/requests'

vi.mock('../context/AuthContext', async () => {
  const actual = await vi.importActual('../context/AuthContext')
  return { ...actual, useAuth: vi.fn() }
})
vi.mock('../api/requests')

const REQUESTER = { user_id: 2, name: 'Rita Requester', role: 'requester' }

const MY_REQUEST = {
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

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/requests/mine" element={<MyRequestsPage />} />
        <Route path="/requests/:id" element={<MyRequestsPage />} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  AuthContextModule.useAuth.mockReturnValue({ token: 'requester-token', user: REQUESTER })
  requestsApi.getMyRequests.mockResolvedValue({
    items: [MY_REQUEST],
    total: 1,
    page: 1,
    page_size: 25,
    total_pages: 1,
  })
  requestsApi.getMyRequestsSummary.mockResolvedValue({ total: 1, by_status: { open: 1 } })
  requestsApi.getRequestComments.mockResolvedValue([])
})

describe('MyRequestsPage deep link', () => {
  it('auto-expands the matching request when visited directly by the owning requester', async () => {
    renderAt('/requests/1')

    await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument())
    // Only visible in the expanded detail row, not the collapsed table row.
    await waitFor(() => expect(screen.getByText(/waiting for a reviewer/i)).toBeInTheDocument())
    expect(screen.queryByText(/was not found/i)).not.toBeInTheDocument()
  })

  it('shows a not-found notice instead of leaking another user\'s request', async () => {
    // getMyRequests is scoped server-side to the caller, so a request that
    // belongs to someone else simply never appears in this list.
    renderAt('/requests/999')

    await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument())
    expect(screen.getByText(/Request #999 was not found in your requests/i)).toBeInTheDocument()
    // Own request row is present in the list (as always) but nothing is
    // auto-expanded, since the deep-linked ID never matched anything here.
    expect(screen.queryByText(/waiting for a reviewer/i)).not.toBeInTheDocument()
  })
})

describe('MyRequestsPage pagination', () => {
  it('shows pagination controls and requests the next page on click', async () => {
    requestsApi.getMyRequests.mockResolvedValue({
      items: [MY_REQUEST],
      total: 60,
      page: 1,
      page_size: 25,
      total_pages: 3,
    })
    renderAt('/requests/mine')
    await waitFor(() => expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    await waitFor(() => {
      expect(requestsApi.getMyRequests).toHaveBeenCalledWith(
        'requester-token',
        expect.objectContaining({ page: 2 })
      )
    })
  })

  it('resets to page 1 when the status filter changes after navigating to a later page', async () => {
    requestsApi.getMyRequests.mockResolvedValue({
      items: [MY_REQUEST],
      total: 60,
      page: 1,
      page_size: 25,
      total_pages: 3,
    })
    renderAt('/requests/mine')
    await waitFor(() => expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(requestsApi.getMyRequests).toHaveBeenCalledWith(
        'requester-token',
        expect.objectContaining({ page: 2 })
      )
    })

    fireEvent.click(screen.getByText('Status: all'))
    fireEvent.click(screen.getByRole('button', { name: 'open' }))

    await waitFor(() => {
      expect(requestsApi.getMyRequests).toHaveBeenCalledWith(
        'requester-token',
        expect.objectContaining({ status: 'open', page: 1 })
      )
    })
  })
})
