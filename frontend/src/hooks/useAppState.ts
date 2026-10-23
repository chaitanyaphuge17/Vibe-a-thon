import { useCallback, useEffect, useRef, useState } from 'react'
import { getState } from '../api'
import type { State } from '../types'

export interface AppStateResult {
  state: State | null
  loading: boolean
  connected: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useAppState(): AppStateResult {
  const [state, setState] = useState<State | null>(null)
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const next = await getState()
      if (!mounted.current) return
      setState(next)
      setConnected(true)
      setError(null)
    } catch (reason) {
      if (!mounted.current) return
      setConnected(false)
      setError(reason instanceof Error ? reason.message : 'Backend unreachable')
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    const interval = window.setInterval(() => void refresh(), 2000)
    return () => {
      mounted.current = false
      window.clearInterval(interval)
    }
  }, [refresh])

  return { state, loading, connected, error, refresh }
}
