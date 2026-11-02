/** Formatting helpers. Every one is total: bad input renders as an em dash. */

const NUMBER_FORMAT = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
const COMPACT_FORMAT = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export function formatNumber(value: unknown): string {
  const n = toFiniteNumber(value)
  return n === null ? '—' : NUMBER_FORMAT.format(n)
}

export function formatCompact(value: unknown): string {
  const n = toFiniteNumber(value)
  return n === null ? '—' : COMPACT_FORMAT.format(n)
}

export function pluralize(count: number, singular: string, plural?: string): string {
  const word = count === 1 ? singular : (plural ?? `${singular}s`)
  return `${formatNumber(count)} ${word}`
}

/**
 * Normalise a confidence to 0..100. Current backends send 0..1; a value
 * already expressed as a percentage is accepted so a UI never shows 7000%.
 */
export function confidencePercent(value: unknown): number | null {
  const n = toFiniteNumber(value)
  if (n === null) return null
  const percent = n >= 0 && n <= 1 ? n * 100 : n
  return Math.max(0, Math.min(100, Math.round(percent)))
}

export function formatConfidence(value: unknown): string {
  const percent = confidencePercent(value)
  return percent === null ? '—' : `${percent}%`
}

/** Latency in ms, rendered for a human: 8 ms, 1.24 s, 2.1 min. */
export function formatLatency(value: unknown): string {
  const ms = toFiniteNumber(value)
  if (ms === null) return '—'
  if (ms < 1) return '<1 ms'
  if (ms < 1_000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1_000).toFixed(2)} s`
  return `${(ms / 60_000).toFixed(1)} min`
}

/** Elapsed seconds as mm:ss or h:mm:ss. */
export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(Number.isFinite(totalSeconds) ? totalSeconds : 0))
  const hours = Math.floor(seconds / 3_600)
  const minutes = Math.floor((seconds % 3_600) / 60)
  const rest = seconds % 60
  const two = (n: number) => String(n).padStart(2, '0')
  return hours > 0 ? `${hours}:${two(minutes)}:${two(rest)}` : `${two(minutes)}:${two(rest)}`
}

/** "compare_periods" -> "Compare periods" (sentence case, for labels). */
export function humanize(key: string): string {
  const words = key
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .trim()
    .toLowerCase()
  if (!words) return ''
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function truncate(text: string, max = 90): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (clean.length <= max) return clean
  const cut = clean.slice(0, Math.max(0, max - 1)).trimEnd()
  return `${cut}…`
}

/** Escape untrusted text before it reaches an HTML tooltip formatter. */
export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

/** Any cell value as safe display text. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) {
    return value.length === 0 ? '—' : value.map((item) => formatValue(item)).join(', ')
  }
  if (typeof value === 'object') {
    try {
      return truncate(JSON.stringify(value), 160)
    } catch {
      return '[unrenderable value]'
    }
  }
  return String(value)
}

/** ISO-ish timestamps rendered as a short local date; anything else as-is. */
export function formatAsOf(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) return '—'
  const text = value.trim()
  if (!/^\d{4}-\d{2}-\d{2}/.test(text)) return text
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) return text
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}
