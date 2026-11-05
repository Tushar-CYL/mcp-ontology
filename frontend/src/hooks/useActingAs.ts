import { useState } from 'react'

const ACTING_KEY = 'strata.actingAs'

/** Who is making decisions. Kept per browser; every decision is audited. */
export function useActingAs(): [string, (name: string) => void] {
  const [name, setName] = useState<string>(() => {
    try {
      return window.localStorage.getItem(ACTING_KEY) || 'steward'
    } catch {
      return 'steward'
    }
  })
  const update = (value: string) => {
    setName(value)
    try {
      window.localStorage.setItem(ACTING_KEY, value)
    } catch {
      /* storage blocked: keep it for this session only */
    }
  }
  return [name, update]
}
