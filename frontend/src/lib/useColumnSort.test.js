import { renderHook, act } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { useColumnSort } from './useColumnSort'

describe('useColumnSort', () => {
  it('starts on the default column, ascending', () => {
    const { result } = renderHook(() => useColumnSort('created', ['priority', 'created']))
    expect(result.current.activeColumn).toBe('created')
    expect(result.current.direction).toBe('asc')
  })

  it('toggling the active column flips its direction', () => {
    const { result } = renderHook(() => useColumnSort('created', ['priority', 'created']))

    act(() => result.current.toggleColumn('created'))
    expect(result.current.activeColumn).toBe('created')
    expect(result.current.direction).toBe('desc')

    act(() => result.current.toggleColumn('created'))
    expect(result.current.direction).toBe('asc')
  })

  it('switching to a different column does not reset its remembered direction', () => {
    const { result } = renderHook(() => useColumnSort('created', ['priority', 'created']))

    // switch to priority (starts 'asc'), then toggle it to 'desc'
    act(() => result.current.toggleColumn('priority'))
    expect(result.current.activeColumn).toBe('priority')
    act(() => result.current.toggleColumn('priority'))
    expect(result.current.direction).toBe('desc')

    // switch to created (still default 'asc') and back to priority — priority
    // should still remember 'desc', not have been reset to 'asc'
    act(() => result.current.toggleColumn('created'))
    expect(result.current.activeColumn).toBe('created')
    expect(result.current.direction).toBe('asc')

    act(() => result.current.toggleColumn('priority'))
    expect(result.current.activeColumn).toBe('priority')
    expect(result.current.direction).toBe('desc')
  })
})
