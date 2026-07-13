import { render, screen, waitFor, act } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import * as authApi from '../api/auth'

vi.mock('../api/auth')

const PROFILE = { user_id: 1, name: 'Ada Lovelace', email: 'ada@example.com', role: 'requester' }

function TestConsumer() {
  const { user, token, loading, signIn, signOut, justLoggedIn, clearJustLoggedIn } = useAuth()
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="user">{user ? user.name : 'none'}</div>
      <div data-testid="token">{token || 'none'}</div>
      <div data-testid="justLoggedIn">{String(justLoggedIn)}</div>
      <button onClick={() => signIn('ada@example.com', 'pw')}>login</button>
      <button onClick={signOut}>logout</button>
      <button onClick={clearJustLoggedIn}>clear-just-logged-in</button>
    </div>
  )
}

function renderWithProviders() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

describe('AuthContext', () => {
  it('starts logged out when there is no stored token', async () => {
    renderWithProviders()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))
    expect(screen.getByTestId('user')).toHaveTextContent('none')
    expect(authApi.getCurrentUser).not.toHaveBeenCalled()
  })

  it('signIn stores the token and loads the profile via /users/me (not the full user list)', async () => {
    authApi.login.mockResolvedValue({ access_token: 'fake-token' })
    authApi.getCurrentUser.mockResolvedValue(PROFILE)

    renderWithProviders()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByText('login'))

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('Ada Lovelace'))
    expect(localStorage.getItem('requestflow_token')).toBe('fake-token')
    expect(authApi.getCurrentUser).toHaveBeenCalledWith('fake-token')
  })

  it('signOut clears the token and user', async () => {
    authApi.login.mockResolvedValue({ access_token: 'fake-token' })
    authApi.getCurrentUser.mockResolvedValue(PROFILE)
    renderWithProviders()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))
    fireEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('Ada Lovelace'))

    fireEvent.click(screen.getByText('logout'))

    expect(screen.getByTestId('user')).toHaveTextContent('none')
    expect(localStorage.getItem('requestflow_token')).toBeNull()
  })

  it('treats a stored token that fails to resolve to a profile as logged out', async () => {
    localStorage.setItem('requestflow_token', 'stale-token')
    authApi.getCurrentUser.mockRejectedValue(new Error('401'))

    renderWithProviders()

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))
    expect(screen.getByTestId('user')).toHaveTextContent('none')
    expect(localStorage.getItem('requestflow_token')).toBeNull()
  })

  it('signIn sets justLoggedIn, but restoring a stored token on mount does not', async () => {
    authApi.getCurrentUser.mockResolvedValue(PROFILE)
    localStorage.setItem('requestflow_token', 'stale-token')

    renderWithProviders()
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('Ada Lovelace'))
    expect(screen.getByTestId('justLoggedIn')).toHaveTextContent('false')

    authApi.login.mockResolvedValue({ access_token: 'fake-token' })
    fireEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('justLoggedIn')).toHaveTextContent('true'))
  })

  it('clearJustLoggedIn resets the flag (consumed once, so it does not keep reopening the widget)', async () => {
    authApi.login.mockResolvedValue({ access_token: 'fake-token' })
    authApi.getCurrentUser.mockResolvedValue(PROFILE)
    renderWithProviders()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('justLoggedIn')).toHaveTextContent('true'))

    fireEvent.click(screen.getByText('clear-just-logged-in'))
    expect(screen.getByTestId('justLoggedIn')).toHaveTextContent('false')
  })

  it('reacts to the auth:unauthorized event (fired by apiFetch on any 401) by signing out', async () => {
    localStorage.setItem('requestflow_token', 'good-token')
    authApi.getCurrentUser.mockResolvedValue(PROFILE)

    renderWithProviders()
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('Ada Lovelace'))

    act(() => {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    })

    expect(screen.getByTestId('user')).toHaveTextContent('none')
    expect(localStorage.getItem('requestflow_token')).toBeNull()
  })
})
