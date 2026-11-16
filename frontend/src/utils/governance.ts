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

/** The path every source takes: connect it, the three tools, then agents. */
export const LAYER_FLOW = [
  { label: 'Source', to: '/onboarding', layer: null },
  { label: 'Ontology', to: '/tools/ontology', layer: 'ontology' },
  { label: 'Knowledge graph', to: '/tools/graph', layer: 'graph' },
  { label: 'Semantic', to: '/tools/semantic', layer: 'semantic' },
  { label: 'Context', to: '/tools/context', layer: 'context' },
  { label: 'Agents', to: '/agents', layer: null },
] as const
