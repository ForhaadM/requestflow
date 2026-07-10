import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { UsersProvider, useUsers } from './UsersContext'
import * as authApi from '../api/auth'
import * as AuthContextModule from './AuthContext'

vi.mock('../api/auth')
vi.mock('./AuthContext', async () => {
  const actual = await vi.importActual('./AuthContext')
  return { ...actual, useAuth: vi.fn() }
})

function Consumer() {
  const { users, loading, nameFor } = useUsers()
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="count">{users.length}</div>
      <div data-testid="name">{nameFor(2)}</div>
    </div>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  AuthContextModule.useAuth.mockReturnValue({ token: 'fake-token' })
})

describe('UsersContext', () => {
  it('lazily fetches the user directory (GET /users) on first use', async () => {
    authApi.getUsers.mockResolvedValue([
      { user_id: 1, name: 'Alice', email: 'a@example.com', role: 'admin' },
      { user_id: 2, name: 'Bob', email: 'b@example.com', role: 'reviewer' },
    ])

    render(
      <UsersProvider>
        <Consumer />
      </UsersProvider>
    )

    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('2'))
    expect(screen.getByTestId('name')).toHaveTextContent('Bob')
    expect(authApi.getUsers).toHaveBeenCalledWith('fake-token')
    expect(authApi.getUsers).toHaveBeenCalledTimes(1)
  })

  it('does not re-fetch for a second consumer once already loaded', async () => {
    authApi.getUsers.mockResolvedValue([{ user_id: 1, name: 'Alice', email: 'a@example.com', role: 'admin' }])

    render(
      <UsersProvider>
        <Consumer />
        <Consumer />
      </UsersProvider>
    )

    await waitFor(() => expect(screen.getAllByTestId('count')[0]).toHaveTextContent('1'))
    expect(authApi.getUsers).toHaveBeenCalledTimes(1)
  })

  it('falls back to a placeholder name for an unknown user id', async () => {
    authApi.getUsers.mockResolvedValue([])
    render(
      <UsersProvider>
        <Consumer />
      </UsersProvider>
    )
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))
    expect(screen.getByTestId('name')).toHaveTextContent('user #2')
  })

  it('does not fetch before a token is available', () => {
    AuthContextModule.useAuth.mockReturnValue({ token: null })
    render(
      <UsersProvider>
        <Consumer />
      </UsersProvider>
    )
    expect(authApi.getUsers).not.toHaveBeenCalled()
  })
})
