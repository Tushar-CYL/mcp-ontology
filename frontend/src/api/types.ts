/**
 * Typed response models for the Middle Layer HTTP API (base `/api`).
 *
 * The shapes follow the published contract. Everything the backend may omit
 * is marked optional so the UI degrades into a clear empty state rather than
 * crashing on a missing field.
 */

// ------------------------------------------------------------------ health
export interface HealthResponse {
  status: string
  sources: string[]
}

// ----------------------------------------------------------------- sources
export interface SourceSummary {
  id: string
  name?: string
  origin: string
  tables: number
  classes: number
  relations: number
  nodes: number
  edges: number
  status: string
  warnings: string[]
}

export interface SourcesResponse {
  sources: SourceSummary[]
}

export interface CreateSourceRequest {
  path: string
  name?: string
}

/** `POST /api/sources` returns the same summary shape as a listed source. */
export type CreateSourceResponse = SourceSummary

// ---------------------------------------------------------------- ontology
export interface OntologyClass {
  name: string
  table: string
  key: string
  /** Present on newer backends: the key was invented because none existed. */
  key_is_synthetic?: boolean
  time_column?: string | null
  count: number
  measures: string[]
  dimensions?: string[]
}

export interface OntologyRelation {
  name: string
  domain: string
  range: string
  /** "measured" means the source declared the link; anything else was derived. */
  provenance: string
  /** 0..1 on current backends; tolerated as 0..100 by the formatter. */
  confidence: number
  count: number
}

export interface OntologyResponse {
  source: string
  classes: OntologyClass[]
  relations: OntologyRelation[]
}

// ------------------------------------------------------------------- graph
export interface GraphNode {
  id: string
  key?: string
  label: string
  class: string
  degree: number
  source?: string
}

export interface GraphEdge {
  source: string
  target: string
  relation: string
  provenance?: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ---------------------------------------------------------------- semantic
export interface MetricSummary {
  name: string
  title: string
  description: string
  unit: string
  owner: string
  status: string
  dimensions?: string[]
}

export interface MetricsResponse {
  metrics: MetricSummary[]
}

export type MetricRow = unknown[] | Record<string, unknown>

export interface EvaluateMetricRequest {
  source: string
  filters?: Record<string, string>
  group_by?: string
  time_from?: string
  time_to?: string
}

export interface EvaluateMetricResponse {
  rows: MetricRow[]
  sql: string
  params?: unknown[]
}

// ----------------------------------------------------------------- context
export interface ContextFocus {
  source?: string
  class?: string
  key?: string
}

export interface ContextFact {
  text: string
  provenance?: string
  citation?: string
  as_of?: string | null
  [key: string]: unknown
}

export interface ContextResponse {
  focus: ContextFocus | string | null
  answer: string
  facts: ContextFact[]
  dropped: ContextFact[]
  sources: string[]
  review_pending: number
  chars: number
  rendered: string
  budget_chars?: number
}

export interface ContextQuery {
  source: string
  class: string
  key: string
  budget_chars?: number
}

// ------------------------------------------------------------------- tools
export interface ToolSummary {
  name: string
  description: string
}

export interface ToolsResponse {
  tools: ToolSummary[]
}

// ------------------------------------------------------------------ agents
export const AGENT_SKILLS = [
  'explain_metric',
  'compare_periods',
  'breakdown_by',
  'graph_context',
  'evidence_search',
] as const

export type AgentSkill = (typeof AGENT_SKILLS)[number]

export interface SkillDefinition {
  id: string
  name?: string
  label?: string
  description: string
  builtin: boolean
  source?: string
  kind?: string
  metric?: string
  dimension?: string
  status?: string
}

export interface SkillsResponse {
  skills: SkillDefinition[]
}

export interface CreateSkillRequest {
  name: string
  description: string
  source_id: string
  kind: 'metric_focus' | 'comparison' | 'breakdown'
  metric: string
  dimension?: string
}

export interface CertificationCheck {
  name: string
  passed: boolean
  detail: string
  severity: 'ok' | 'warning' | 'error' | string
}

export interface CertificationLayer {
  layer: string
  status: 'pass' | 'warn' | 'fail' | string
  passed: number
  total: number
  checks: CertificationCheck[]
}

export interface GuardrailSuggestion {
  id: string
  label: string
  instruction: string
  enabled: boolean
  source: string
}

export interface SourceGuardrailsResponse {
  source_id: string
  rules: GuardrailSuggestion[]
}

export interface GuardrailSuggestResponse {
  guardrails: GuardrailSuggestion[]
  configured: boolean
}

export interface CertificationResponse {
  source: string
  certified: boolean
  status: 'pass' | 'warn' | 'fail' | string
  generated_at: string
  metric_used?: string | null
  layers: CertificationLayer[]
}

export interface Agent {
  id: string
  name: string
  purpose?: string
  problem_statement?: string
  instructions?: string
  metrics?: string[]
  /** Canonical source scope. Older payloads may only carry `source`. */
  sources?: string[]
  source?: string
  source_scope?: string
  guardrails?: string[]
  skills?: string[]
  status?: string
  published?: boolean
  created_at?: string
  updated_at?: string
}

export interface AgentsResponse {
  agents: Agent[]
}

export interface AgentDraft {
  name: string
  purpose: string
  problem_statement: string
  instructions: string
  sources: string[]
  metrics: string[]
  guardrails: string[]
  skills: string[]
}

export interface PreviewRequest {
  question: string
}

export interface PreviewResponse {
  answer: AgentAnswer
  evidence?: Evidence
  latency_ms?: number
}

export interface PublishResponse {
  status: string
}

// ------------------------------------------------------------------ answers
export interface AnswerSections {
  summary?: string
  cause?: string
  impact?: string
  recommendation?: string
  [key: string]: unknown
}

export type AgentAnswer = string | AnswerSections

/** A fact as returned in agent evidence; tolerant of legacy string facts. */
export interface EvidenceFact {
  text?: string
  label?: string
  value?: unknown
  citation?: string
  provenance?: string
  as_of?: string | null
  [key: string]: unknown
}

export interface TraceStep {
  tool?: string
  name?: string
  args?: unknown
  result?: unknown
  args_summary?: string
  result_summary?: string
  latency_ms?: number
  [key: string]: unknown
}

export interface SourceRecord {
  table?: string
  columns?: string[]
  rows?: Array<Record<string, unknown>>
  redacted_columns?: string[]
}

export interface PriorEvidence {
  metric?: string
  title?: string
  prior?: number | null
  current?: number | null
  change?: number | null
  change_pct?: number | null
  prior_window?: { from?: string; to?: string }
  current_window?: { from?: string; to?: string }
}

export interface EvidenceLineage {
  definitions?: Array<{ metric?: string; definition?: Record<string, unknown> }>
  sql?: string[]
}

export interface Evidence {
  facts?: Array<EvidenceFact | string>
  trace?: TraceStep[]
  sources?: string[]
  confidence?: number
  relationships?: unknown[]
  source_records?: SourceRecord[]
  prior_evidence?: PriorEvidence[]
  lineage?: EvidenceLineage
  [key: string]: unknown
}

export interface AskResponse {
  run_id: string
  question?: string
  answer: AgentAnswer
  evidence: Evidence
  sources?: string[]
  latency_ms?: number
}

export type RunResponse = AskResponse
