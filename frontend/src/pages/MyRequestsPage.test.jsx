import { render, screen, waitFor } from '@testing-library/react'
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
  requestsApi.getMyRequests.mockResolvedValue([MY_REQUEST])
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
