import type { Agent, AgentKey } from '../api/types'

const PLACEHOLDER = '<YOUR_KEY>'

/** Put a freshly issued key into a config snippet. Without one, keep the
 * placeholder: the secret is shown once and never fetched again. */
export function fillKey(snippet: string, key: string | null | undefined): string {
  return key ? snippet.split(PLACEHOLDER).join(key) : snippet
}

export type Tone = 'teal' | 'rose' | 'neutral'

export function keyStatus(key: Pick<AgentKey, 'revoked' | 'last_used_at'>): {
  label: string
  tone: Tone
} {
  if (key.revoked) return { label: 'Revoked', tone: 'rose' }
  if (!key.last_used_at) return { label: 'Never used', tone: 'neutral' }
  return { label: 'Active', tone: 'teal' }
}

/** The API has carried an agent's source as source_id, sources or source. */
export function agentSource(agent: Agent): string {
  return agent.source_id || agent.sources?.[0] || agent.source || ''
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

export function toolLabel(name: string): string {
  const words = name.replace(/_/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}
