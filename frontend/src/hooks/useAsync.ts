import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'
import { isAbortError } from '../api/client'

export interface AsyncResult<T> {
  data: T | undefined
  error: unknown
  loading: boolean
  /** True only for the first load, so refetches can keep stale data visible. */
  initialLoading: boolean
  reload: () => void
}

/**
 * Small data-loading hook: one AbortController per run, stale results
 * discarded, cancellations never shown as errors. `deps` drives refetches.
 */
export function useAsync<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList,
  options: { enabled?: boolean } = {},
): AsyncResult<T> {
  const enabled = options.enabled ?? true
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<unknown>(undefined)
  const [loading, setLoading] = useState(enabled)
  const [loadedOnce, setLoadedOnce] = useState(false)
  const [tick, setTick] = useState(0)

  const reload = useCallback(() => setTick((value) => value + 1), [])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      setData(undefined)
      setError(undefined)
      setLoadedOnce(false)
      return
    }

    const controller = new AbortController()
    let active = true
    setLoading(true)
    setError(undefined)

    loaderRef
      .current(controller.signal)
      .then((result) => {
        if (!active) return
        setData(result)
        setLoading(false)
        setLoadedOnce(true)
      })
      .catch((cause: unknown) => {
        if (!active || isAbortError(cause)) return
        setError(cause)
        setLoading(false)
        setLoadedOnce(true)
      })

    return () => {
      active = false
      controller.abort()
    }
    // The loader is read through a ref on purpose; deps define identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, tick])

  return {
    data,
    error,
    loading,
    initialLoading: loading && !loadedOnce,
    reload,
  }
}
