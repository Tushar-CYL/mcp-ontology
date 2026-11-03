/** Split a comma- or line-separated list typed by a steward. */
export function parseList(text: string): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const raw of text.split(/[,\n]/)) {
    const value = raw.trim()
    const key = value.toLowerCase()
    if (value && !seen.has(key)) {
      seen.add(key)
      out.push(value)
    }
  }
  return out
}

export function validationTone(status: string): 'teal' | 'amber' | 'rose' | 'neutral' {
  if (status === 'pass') return 'teal'
  if (status === 'warn') return 'amber'
  if (status === 'fail') return 'rose'
  return 'neutral'
}

export function verdictTone(verdict: string | undefined): 'teal' | 'amber' | 'rose' | 'neutral' {
  if (verdict === 'yes') return 'teal'
  if (verdict === 'partial') return 'amber'
  if (verdict === 'no') return 'rose'
  return 'neutral'
}

/** The path every source takes: connect it, four layers, then agents. */
export const LAYER_FLOW = [
  { label: 'Source', to: '/onboarding', layer: null },
  { label: '1 Ontology', to: '/layers/ontology', layer: 'ontology' },
  { label: '2 Knowledge graph', to: '/layers/graph', layer: 'graph' },
  { label: '3 Semantic', to: '/layers/semantic', layer: 'semantic' },
  { label: '4 Context', to: '/layers/context', layer: 'context' },
  { label: 'Agents', to: '/agents', layer: null },
] as const
