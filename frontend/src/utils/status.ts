import type { BadgeTone } from '../components/Badge'

/** Map a backend status string to a badge tone, tolerantly. */
export function statusTone(status: unknown): BadgeTone {
  const value = typeof status === 'string' ? status.trim().toLowerCase() : ''
  if (/^(ready|ok|online|connected|built|complete|completed|published|active|live|healthy)$/.test(value)) {
    return 'teal'
  }
  if (/^(building|reading|loading|pending|queued|running|draft|proposed|checking|starting)$/.test(value)) {
    return 'amber'
  }
  if (/^(error|failed|failure|offline|unreachable|rejected|invalid)$/.test(value)) {
    return 'rose'
  }
  return 'neutral'
}

/** A short, human status label; the backend value is kept when unknown. */
export function statusLabel(status: unknown): string {
  if (typeof status !== 'string' || !status.trim()) return 'Unknown'
  const value = status.trim().toLowerCase()
  if (value === 'ok') return 'Ready'
  if (value === 'built' || value === 'complete' || value === 'completed') return 'Built'
  return status.trim().charAt(0).toUpperCase() + status.trim().slice(1)
}
