import { useEffect, useRef, useState } from 'react'

/** Seconds elapsed since `active` became true; survives re-renders. */
export function useElapsed(active: boolean): number {
  const [seconds, setSeconds] = useState(0)
  const startedRef = useRef<number | null>(null)

  useEffect(() => {
    if (!active) {
      startedRef.current = null
      setSeconds(0)
      return
    }

    startedRef.current = Date.now()
    setSeconds(0)
    const timer = window.setInterval(() => {
      if (startedRef.current === null) return
      setSeconds((Date.now() - startedRef.current) / 1_000)
    }, 250)

    return () => window.clearInterval(timer)
  }, [active])

  return seconds
}
