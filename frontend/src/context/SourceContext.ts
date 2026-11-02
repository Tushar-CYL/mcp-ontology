import { createContext, useContext } from 'react'
import type { HealthResponse, SourceSummary } from '../api/types'

export interface SourceApi {
  sources: SourceSummary[]
  selectedId: string | null
  selectedSource: SourceSummary | null
  health: HealthResponse | null
  healthError: unknown
  loading: boolean
  error: unknown
  refresh: () => Promise<void>
  selectSource: (id: string) => void
}

export const SourceContext = createContext<SourceApi | null>(null)

export function useSource(): SourceApi {
  const context = useContext(SourceContext)
  if (context === null) {
    throw new Error('useSource must be used inside <SourceProvider>')
  }
  return context
}
