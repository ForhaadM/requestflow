import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { RequestDetailPanel } from './RequestDetailPanel'
import * as requestsApi from '../api/requests'

vi.mock('../api/requests', () => ({
  getRequestComments: vi.fn(),
  addRequestComment: vi.fn(),
}))

const request = {
  request_id: 1,
  priority: 'P1',
  created_at: '2026-07-17T00:00:00',
  description: 'Need a monitor',
  urgency_justification: null,
}

beforeEach(() => {
  requestsApi.getRequestComments.mockResolvedValue([])
})

describe('RequestDetailPanel', () => {
  it('renders the SLA badge for a reviewer/admin viewer (per-ticket countdown, not just the requester view)', async () => {
    render(<RequestDetailPanel request={request} token="t" canAddComment={false} currentUserId={2} />)
    // SlaBadge renders a countdown/breach label sourced from lib/sla.js — assert
    // it's present at all here, since the point being tested is that this
    // shared panel (used by ReviewQueuePage/CompletedReviewsPage) surfaces it,
    // not the exact wording (covered by sla.js's own logic elsewhere).
    await waitFor(() => {
      expect(screen.getByText(/left|breached/i)).toBeInTheDocument()
    })
  })

  it('shows the "Add comment" input when canAddComment is true (e.g. the claiming reviewer, or an admin)', async () => {
    render(<RequestDetailPanel request={request} token="t" canAddComment currentUserId={2} />)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Add a comment…')).toBeInTheDocument()
    })
  })

  it('hides the "Add comment" input when canAddComment is false (e.g. a non-claiming reviewer)', async () => {
    render(<RequestDetailPanel request={request} token="t" canAddComment={false} currentUserId={2} />)
    await waitFor(() => {
      expect(requestsApi.getRequestComments).toHaveBeenCalled()
    })
    expect(screen.queryByPlaceholderText('Add a comment…')).not.toBeInTheDocument()
  })

  it('labels the viewer\'s own comment "You" and other authors by their commenter_name', async () => {
    requestsApi.getRequestComments.mockResolvedValue([
      { comment_id: 1, commenter_reference: 2, commenter_name: 'Riley Reviewer', comment_text: 'Working on it', created_at: '2026-07-17T00:00:00' },
      { comment_id: 2, commenter_reference: 5, commenter_name: 'Quinn Requester', comment_text: 'Thanks!', created_at: '2026-07-17T01:00:00' },
    ])
    render(<RequestDetailPanel request={request} token="t" canAddComment currentUserId={2} />)
    await waitFor(() => {
      expect(screen.getByText('You')).toBeInTheDocument()
    })
    expect(screen.getByText('Quinn Requester')).toBeInTheDocument()
  })
})
