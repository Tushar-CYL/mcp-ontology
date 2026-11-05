import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, isAbortError } from '../api/client'
import type { HealthResponse, SourceSummary } from '../api/types'
import { SourceContext, type SourceApi } from '../context/SourceContext'

const STORAGE_KEY = 'middle-layer:selected-source'
const HEALTH_RETRY_MS = 3_000
const HEALTH_POLL_MS = 45_000

function readStoredSource(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function SourceProvider({ children }: { children: ReactNode }) {
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(readStoredSource)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const applySources = useCallback((list: SourceSummary[]) => {
    setSources(list)
    setSelectedId((current) => {
      if (current && list.some((source) => source.id === current)) return current
      return list[0]?.id ?? null
    })
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    // Health is checked even when the source list fails: that failure is
    // exactly when the top bar must say "API unreachable", not "unknown".
    const checkHealth = async () => {
      try {
        const healthResult = await api.health()
        if (!mounted.current) return
        setHealth(healthResult)
        setHealthError(null)
      } catch (cause) {
        if (mounted.current && !isAbortError(cause)) {
          setHealth(null)
          setHealthError(cause)
        }
      }
    }
    try {
      const listed = await api.listSources()
      if (!mounted.current) return
      applySources(listed.sources)
      setError(null)
    } catch (cause) {
      if (!isAbortError(cause)) setError(cause)
    } finally {
      await checkHealth()
      if (mounted.current) setLoading(false)
    }
  }, [applySources])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // Keep the top-bar status honest without hammering the service.
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      api
        .health()
        .then((result) => {
          if (!mounted.current) return
          setHealth(result)
          setHealthError(null)
        })
        .catch((cause: unknown) => {
          if (!mounted.current || isAbortError(cause)) return
          setHealthError(cause)
        })
    // While the API is unreachable, look again every few seconds so the top
    // bar turns green soon after the server is back.
    }, healthError ? HEALTH_RETRY_MS : HEALTH_POLL_MS)
    return () => window.clearInterval(timer)
  }, [healthError])

  useEffect(() => {
    try {
      if (selectedId) window.localStorage.setItem(STORAGE_KEY, selectedId)
      else window.localStorage.removeItem(STORAGE_KEY)
    } catch {
      // A private-mode browser can refuse storage; selection still works in-session.
    }
  }, [selectedId])

  const selectSource = useCallback((id: string) => setSelectedId(id), [])

  const selectedSource = useMemo(
    () => sources.find((source) => source.id === selectedId) ?? null,
    [sources, selectedId],
  )

  const value = useMemo<SourceApi>(
    () => ({
      sources,
      selectedId,
      selectedSource,
      health,
      healthError,
      loading,
      error,
      refresh,
      selectSource,
    }),
    [sources, selectedId, selectedSource, health, healthError, loading, error, refresh, selectSource],
  )

  return <SourceContext.Provider value={value}>{children}</SourceContext.Provider>
}
