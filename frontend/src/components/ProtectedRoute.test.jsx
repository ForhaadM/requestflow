import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'
import * as AuthContextModule from '../context/AuthContext'

vi.mock('../context/AuthContext', async () => {
  const actual = await vi.importActual('../context/AuthContext')
  return { ...actual, useAuth: vi.fn() }
})

function renderProtectedRoute(authState, { allowedRoles } = {}) {
  AuthContextModule.useAuth.mockReturnValue(authState)
  return render(
    <MemoryRouter initialEntries={['/protected']}>
      <Routes>
        <Route path="/welcome" element={<div>welcome page</div>} />
        <Route path="/" element={<div>home page</div>} />
        <Route element={<ProtectedRoute allowedRoles={allowedRoles} />}>
          <Route path="/protected" element={<div>secret content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  it('shows a loading state while auth is still resolving', () => {
    renderProtectedRoute({ token: null, user: null, loading: true })
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('redirects to /welcome when there is no token', () => {
    renderProtectedRoute({ token: null, user: null, loading: false })
    expect(screen.getByText('welcome page')).toBeInTheDocument()
    expect(screen.queryByText('secret content')).not.toBeInTheDocument()
  })

  it('redirects to / when the user role is not in allowedRoles', () => {
    renderProtectedRoute(
      { token: 't', user: { role: 'requester' }, loading: false },
      { allowedRoles: ['admin'] }
    )
    expect(screen.getByText('home page')).toBeInTheDocument()
    expect(screen.queryByText('secret content')).not.toBeInTheDocument()
  })

  it('renders the protected content when the role is allowed', () => {
    renderProtectedRoute(
      { token: 't', user: { role: 'admin' }, loading: false },
      { allowedRoles: ['admin'] }
    )
    expect(screen.getByText('secret content')).toBeInTheDocument()
  })

  it('renders the protected content when no allowedRoles restriction is set', () => {
    renderProtectedRoute({ token: 't', user: { role: 'requester' }, loading: false })
    expect(screen.getByText('secret content')).toBeInTheDocument()
  })
})
