import { formatAsOf, formatNumber, humanize, truncate } from './format'

/** Tolerant normalisation of a fact that may arrive as a string or an object. */
export interface NormalizedFact {
  text: string
  citation: string
  provenance: string
  asOf: string | null
  raw: unknown
}

export interface NormalizedTraceStep {
  tool: string
  argsSummary: string
  resultSummary: string
  latencyMs: number | null
  raw: unknown
}

function firstString(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

/** Compact one-value preview used for tool arguments and results. */
export function summarizeValue(value: unknown, max = 140): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return truncate(value, max) || '—'
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (Array.isArray(value)) {
    if (value.length === 0) return 'empty list'
    if (value.length <= 2) {
      return truncate(value.map((item) => summarizeValue(item, Math.max(20, Math.floor(max / 2)))).join(', '), max)
    }
    return `${formatNumber(value.length)} items · ${truncate(
      value
        .slice(0, 2)
        .map((item) => summarizeValue(item, 60))
        .join(', '),
      max,
    )}`
  }
  try {
    return truncate(JSON.stringify(value), max)
  } catch {
    return '—'
  }
}

export function normalizeFact(fact: unknown, index = 0): NormalizedFact {
  if (typeof fact === 'string') {
    return {
      text: fact.trim() || `Fact ${index + 1}`,
      citation: '',
      provenance: 'unknown',
      asOf: null,
      raw: fact,
    }
  }

  if (fact !== null && typeof fact === 'object') {
    const record = fact as Record<string, unknown>
    let text = firstString(record, ['text', 'statement', 'claim', 'fact', 'label', 'summary'])
    if (!text) {
      const value = record.value
      if (value !== null && value !== undefined && typeof value !== 'object') {
        text = String(value)
      } else if (value !== null && typeof value === 'object') {
        text = summarizeValue(value, 240)
      }
    }
    if (!text) text = `Fact ${index + 1}`

    const citation = firstString(record, [
      'citation',
      'source_citation',
      'source_ref',
      'reference',
      'evidence_id',
    ])

    let provenance = firstString(record, ['provenance', 'kind', 'source_type', 'origin'])
    if (!provenance) {
      provenance = typeof record.measured === 'boolean' && record.measured ? 'measured' : 'unknown'
    }

    const asOfValue = record.as_of ?? record.asOf ?? record.timestamp ?? record.time
    const asOf = typeof asOfValue === 'string' && asOfValue.trim() ? asOfValue.trim() : null

    return { text, citation, provenance: provenance.toLowerCase(), asOf, raw: fact }
  }

  return {
    text: fact === null || fact === undefined ? `Fact ${index + 1}` : String(fact),
    citation: '',
    provenance: 'unknown',
    asOf: null,
    raw: fact,
  }
}

export function normalizeFacts(facts: unknown): NormalizedFact[] {
  if (!Array.isArray(facts)) return []
  return facts.map((fact, index) => normalizeFact(fact, index))
}

export function normalizeTrace(trace: unknown): NormalizedTraceStep[] {
  if (!Array.isArray(trace)) return []
  return trace.map((step, index) => {
    if (step === null || typeof step !== 'object') {
      return {
        tool: `step_${index + 1}`,
        argsSummary: '—',
        resultSummary: String(step ?? '—'),
        latencyMs: null,
        raw: step,
      }
    }
    const record = step as Record<string, unknown>
    const tool = firstString(record, ['tool', 'name', 'tool_name', 'action']) || `step_${index + 1}`
    const args = record.args ?? record.arguments ?? record.input
    const result = record.result ?? record.output ?? record.observation
    const argsSummary = firstString(record, ['args_summary', 'arguments_summary', 'input_summary'])
      || summarizeValue(args)
    const resultSummary = firstString(record, ['result_summary', 'output_summary', 'observation_summary'])
      || summarizeValue(result)
    const latencyRaw = record.latency_ms ?? record.duration_ms ?? record.elapsed_ms
    const latencyMs = typeof latencyRaw === 'number' && Number.isFinite(latencyRaw) ? latencyRaw : null
    return { tool, argsSummary, resultSummary, latencyMs, raw: step }
  })
}

export type ProvenanceTone = 'teal' | 'amber' | 'neutral'

export function isMeasured(provenance: string): boolean {
  return /^(measured|stated|declared|exact|observed)$/i.test(provenance.trim())
}

export function provenanceTone(provenance: string): ProvenanceTone {
  if (isMeasured(provenance)) return 'teal'
  if (/^(derived|guessed|inferred|synthetic|unknown|estimated)$/i.test(provenance.trim())) {
    return 'amber'
  }
  return 'neutral'
}

export function provenanceLabel(provenance: string): string {
  if (isMeasured(provenance)) return 'Measured'
  if (/^(derived|guessed|inferred|synthetic|estimated)$/i.test(provenance.trim())) {
    return 'Derived'
  }
  if (!provenance.trim() || provenance === 'unknown') return 'Unlabeled'
  return humanize(provenance)
}

/** Human label for a context fact's provenance (backend uses measured/derived). */
export function contextProvenanceLabel(provenance: unknown): string {
  return provenanceLabel(typeof provenance === 'string' ? provenance : 'unknown')
}

export function formatFactAsOf(asOf: string | null): string {
  return formatAsOf(asOf)
}

/** Assemble the evidence JSON offered by the download button. */
export interface EvidenceRecordInput {
  agentId: string
  agentName: string
  runId: string
  question: string
  answer: unknown
  evidence: unknown
  sources: string[]
  latencyMs: number | null
  trace?: NormalizedTraceStep[]
  facts?: NormalizedFact[]
}

export function buildEvidenceRecord(input: EvidenceRecordInput): Record<string, unknown> {
  return {
    schema: 'middle-layer/evidence@1',
    generated_at: new Date().toISOString(),
    agent: { id: input.agentId, name: input.agentName },
    run_id: input.runId,
    question: input.question,
    answer: input.answer,
    confidence: (input.evidence as { confidence?: unknown } | null)?.confidence ?? null,
    sources: input.sources,
    latency_ms: input.latencyMs,
    trace: input.trace?.map((step) => ({
      tool: step.tool,
      args_summary: step.argsSummary,
      result_summary: step.resultSummary,
      latency_ms: step.latencyMs,
    })) ?? [],
    facts: input.facts?.map((fact) => ({
      text: fact.text,
      citation: fact.citation,
      provenance: fact.provenance,
      as_of: fact.asOf,
    })) ?? [],
    evidence: input.evidence,
  }
}
