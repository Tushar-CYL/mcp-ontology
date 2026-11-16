import { useEffect, useState } from 'react'
import { api, isAbortError } from '../api/client'
import type { OntoSuggestion, SuggestKind } from '../api/types'

export interface Suggestions {
  items: OntoSuggestion[]
  /** "ai" once the AI has picked and completed them; "data" before or without it. */
  method: 'ai' | 'data' | null
  /** True while the AI's picks are still on their way. */
  improving: boolean
}

/**
 * Suggestions taken from this data, for one layer. The data's own
 * suggestions arrive at once; the AI's picks replace them when ready (the
 * server caches them until the ontology changes). `refresh` re-asks, e.g.
 * after a note was added.
 */
export function useSuggestions(oid: string | null | undefined, kind: SuggestKind,
  refresh: unknown = 0, ai = true): Suggestions {
  const [state, setState] = useState<Suggestions>({ items: [], method: null, improving: false })

  useEffect(() => {
    if (!oid) return
    const ctrl = new AbortController()
    let aiDone = false
    setState((s) => ({ ...s, improving: ai }))
    api.ontoSuggest(oid, kind, false, ctrl.signal)
      .then((r) => { if (!aiDone) setState({ items: r.suggestions, method: r.method, improving: ai }) })
      .catch((e) => { if (!isAbortError(e)) setState((s) => ({ ...s, improving: ai })) })
    if (ai) {
      api.ontoSuggest(oid, kind, true, ctrl.signal)
        .then((r) => {
          aiDone = true
          if (r.suggestions.length) setState({ items: r.suggestions, method: r.method, improving: false })
          else setState((s) => ({ ...s, improving: false }))
        })
        .catch((e) => { if (!isAbortError(e)) setState((s) => ({ ...s, improving: false })) })
    }
    return () => ctrl.abort()
  }, [oid, kind, refresh, ai])

  return state
}
