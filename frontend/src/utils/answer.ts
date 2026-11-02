/**
 * The published agent answers with a string or a structured object. The UI
 * wants named sections (cause / impact / recommendation) when they exist and
 * honest prose when they do not, so parsing lives here and is unit tested.
 */

export type SectionKey = 'summary' | 'cause' | 'impact' | 'recommendation'

export interface AnswerSection {
  key: SectionKey
  title: string
  body: string
}

export interface ParsedAnswer {
  /** Text that appeared before any recognised heading. */
  prose: string
  sections: AnswerSection[]
  /** True when at least one named section was recognised. */
  structured: boolean
}

const SECTION_ORDER: SectionKey[] = ['summary', 'cause', 'impact', 'recommendation']

const SECTION_TITLES: Record<SectionKey, string> = {
  summary: 'Summary',
  cause: 'Cause',
  impact: 'Impact',
  recommendation: 'Recommendation',
}

const ALIASES: Record<string, SectionKey> = {
  summary: 'summary',
  overview: 'summary',
  answer: 'summary',
  tldr: 'summary',
  'tl dr': 'summary',
  context: 'summary',
  finding: 'summary',
  findings: 'summary',
  cause: 'cause',
  causes: 'cause',
  'root cause': 'cause',
  'root causes': 'cause',
  why: 'cause',
  reason: 'cause',
  reasons: 'cause',
  explanation: 'cause',
  impact: 'impact',
  impacts: 'impact',
  effect: 'impact',
  effects: 'impact',
  'so what': 'impact',
  consequence: 'impact',
  consequences: 'impact',
  implication: 'impact',
  implications: 'impact',
  recommendation: 'recommendation',
  recommendations: 'recommendation',
  action: 'recommendation',
  actions: 'recommendation',
  'next step': 'recommendation',
  'next steps': 'recommendation',
  'recommended action': 'recommendation',
  'recommended actions': 'recommendation',
}

function canonicalSection(title: string): SectionKey | undefined {
  const normalised = title
    .toLowerCase()
    .replace(/[#*_:]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return ALIASES[normalised]
}

/** Render any section value as readable text rather than [object Object]. */
function stringify(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    return value
      .map((item) => stringify(item))
      .filter(Boolean)
      .join('\n')
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return ''
  }
}

interface HeadingMatch {
  key: SectionKey
  remainder: string
}

function matchHeading(line: string): HeadingMatch | null {
  const patterns: RegExp[] = [
    // ## Cause
    /^\s*#{1,6}\s+([A-Za-z][A-Za-z0-9 /&'’-]{0,40})\s*$/,
    // **Cause:** body
    /^\s*\*\*([A-Za-z][A-Za-z0-9 /&'’-]{0,40}?):?\*\*\s*(.*)$/,
    // **Cause**: body
    /^\s*\*\*([A-Za-z][A-Za-z0-9 /&'’-]{0,40})\*\*\s*:?\s*(.*)$/,
    // Cause: body
    /^\s*([A-Za-z][A-Za-z0-9 /&'’-]{0,40})\s*:\s*(.*)$/,
  ]

  for (const pattern of patterns) {
    const match = pattern.exec(line)
    if (!match) continue
    const title = (match[1] ?? '').trim()
    const key = canonicalSection(title)
    if (key) return { key, remainder: (match[2] ?? '').trim() }
  }
  return null
}

interface ParsedBuckets {
  preamble: string[]
  buckets: Map<SectionKey, string[]>
}

function parsePlainText(text: string): ParsedBuckets {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const preamble: string[] = []
  const buckets = new Map<SectionKey, string[]>()
  let current: SectionKey | null = null

  for (const line of lines) {
    const heading = matchHeading(line)
    if (heading) {
      current = heading.key
      const existing = buckets.get(current) ?? []
      existing.push(heading.remainder)
      buckets.set(current, existing)
      continue
    }
    if (current) {
      buckets.get(current)?.push(line)
    } else {
      preamble.push(line)
    }
  }

  return { preamble, buckets }
}

function parseObjectAnswer(record: Record<string, unknown>): ParsedAnswer {
  const sections: AnswerSection[] = []

  const addSection = (key: SectionKey, value: unknown) => {
    const body = stringify(value)
    if (body) sections.push({ key, title: SECTION_TITLES[key], body })
  }

  // Canonical keys first.
  for (const key of SECTION_ORDER) {
    if (key in record) addSection(key, record[key])
  }

  // Then aliases not already collected.
  for (const [rawKey, value] of Object.entries(record)) {
    const key = canonicalSection(rawKey)
    if (!key || key in record) continue
    if (sections.some((section) => section.key === key)) continue
    addSection(key, value)
  }

  // `sections: [{ title, body }]` is a common alternative shape.
  const list = record.sections
  if (Array.isArray(list)) {
    for (const item of list) {
      if (item === null || typeof item !== 'object') continue
      const entry = item as Record<string, unknown>
      const key = canonicalSection(String(entry.title ?? entry.heading ?? entry.name ?? ''))
      if (!key) continue
      addSection(key, entry.body ?? entry.content ?? entry.text)
    }
  }

  const proseCandidates = ['prose', 'text', 'body', 'message', 'answer_text']
  let prose = ''
  for (const candidate of proseCandidates) {
    const value = record[candidate]
    if (typeof value === 'string' && value.trim()) {
      prose = value.trim()
      break
    }
  }

  const ordered = SECTION_ORDER.flatMap((key) => sections.filter((section) => section.key === key))
  const unique = ordered.filter(
    (section, index) => ordered.findIndex((other) => other.key === section.key) === index,
  )

  if (unique.length === 0) {
    try {
      return {
        prose: prose || JSON.stringify(record, null, 2),
        sections: [],
        structured: false,
      }
    } catch {
      return { prose, sections: [], structured: false }
    }
  }

  return { prose, sections: unique, structured: true }
}

/** Parse an agent answer into a stable shape the page can render. */
export function parseAnswer(answer: unknown): ParsedAnswer {
  if (answer === null || answer === undefined) {
    return { prose: '', sections: [], structured: false }
  }

  if (typeof answer === 'string') {
    const text = answer.trim()
    if (!text) return { prose: '', sections: [], structured: false }

    const { preamble, buckets } = parsePlainText(text)
    const sections = SECTION_ORDER.flatMap((key) => {
      const body = (buckets.get(key) ?? []).join('\n').trim()
      return body ? [{ key, title: SECTION_TITLES[key], body }] : []
    })

    if (sections.length === 0) {
      return { prose: text, sections: [], structured: false }
    }

    return {
      prose: preamble.join('\n').trim(),
      sections,
      structured: true,
    }
  }

  if (typeof answer === 'object') {
    return parseObjectAnswer(answer as Record<string, unknown>)
  }

  return { prose: String(answer), sections: [], structured: false }
}
