/**
 * Typed response models for the Strata HTTP API (base `/api`).
 *
 * The shapes follow the published contract. Everything the backend may omit
 * is marked optional so the UI degrades into a clear empty state rather than
 * crashing on a missing field.
 */

// ------------------------------------------------------------------ health
export interface HealthResponse {
  /** True while saved sources are re-opening in the background. */
  warming?: boolean
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
  /** Words people use for this metric; "sales" finds Revenue. */
  synonyms?: string[]
  dimensions?: string[]
  format?: string
  precision?: number
  higher_is_better?: boolean
  caveats?: string
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
  compare_previous?: boolean
  /** Preview a proposed (draft) metric; never used by agents. */
  preview_draft?: boolean
}

export interface EvaluateMetricResponse {
  rows: MetricRow[]
  sql: string
  params?: unknown[]
  prior?: number | null
  change?: number | null
  change_pct?: number | null
  prior_rows?: MetricRow[]
  prior_window?: { from?: string; to?: string }
  direction?: string
  formatted?: string[]
  definition?: MetricSummary & Record<string, unknown>
  window?: { from?: string; to?: string }
}

export interface MetricHealthCheck {
  name: string
  passed: boolean
  detail: string
  severity?: string
}

export interface MetricHealthResponse {
  metric: string
  source: string
  score: number
  checks: MetricHealthCheck[]
  time_min?: string | null
  time_max?: string | null
  definition: MetricSummary
}

export interface MetricContributor {
  key: string
  value: number | null
  prior: number | null
  change: number | null
  change_pct: number | null
  contribution_pct: number | null
}

export interface MetricInsightPoint {
  period: string
  value: number | null
}

export interface LoadJob {
  id: string
  status: 'running' | 'done' | 'failed'
  path: string
  name: string | null
  steps: Array<{ t: number; text: string }>
  result: CreateSourceResponse | null
  error: string | null
  elapsed_s: number
}

export interface MetricInsightsResponse {
  grain?: 'day' | 'week' | 'month' | 'quarter' | 'year'
  time_range?: { min: string | null; max: string | null }
  metric: string
  definition: MetricSummary
  current: EvaluateMetricResponse
  comparison: EvaluateMetricResponse
  trend: MetricInsightPoint[]
  contributors: MetricContributor[]
  dimension?: string | null
}

// ----------------------------------------------------------------- context
export interface ContextFocus {
  source?: string
  class?: string
  key?: string
  type?: string
  question?: string
  metric?: string
  period?: string
  filters?: Record<string, string>
}

export interface ContextFact {
  text: string
  provenance?: string
  citation?: string
  as_of?: string | null
  weight?: number
  relevance?: number
  confidence?: number
  kind?: string
  reason?: string
  [key: string]: unknown
}

export interface ContextCoverage {
  score: number
  present: string[]
  missing: string[]
}

/** yes / partial / no, checked before an answer is given. */
export interface Answerable {
  verdict: 'yes' | 'partial' | 'no'
  reason: string
  nearest_metric: string | null
}

export interface ReceiptLayer {
  layer: 'ontology' | 'graph' | 'semantic' | 'context'
  used: boolean
  summary: string
}

/** Which of the four layers an answer used, in plain words. */
export interface Receipt {
  layers: ReceiptLayer[]
  text: string
}

export interface ContextCharts {
  trend: Array<{ period: string; value: number | null }>
  breakdown: {
    dimension: string | null
    rows: Array<{ key: string; current: number | null; prior: number | null; change: number | null }>
  }
}

export interface SuggestedQuestion {
  text: string
  preset: string
  layer: string
}

export interface ContextSuggestions {
  source: string
  questions: SuggestedQuestion[]
  note: string
}

export interface ContextResponse {
  charts?: ContextCharts
  answerable?: Answerable
  receipt?: Receipt
  focus: ContextFocus | string | null
  answer: string
  facts: ContextFact[]
  dropped: ContextFact[]
  sources: string[]
  review_pending: number
  chars: number
  rendered: string
  budget_chars?: number
  coverage?: ContextCoverage
  metric?: MetricSummary
  period?: { label?: string; from?: string; to?: string; prior_from?: string }
  filters?: Record<string, string>
}

export interface ContextQuery {
  source: string
  class?: string
  key?: string
  question?: string
  metric?: string
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
  /** True when the server answered from its per-source cache. */
  cached?: boolean
  checked_at?: string
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
  source_id?: string
  source_scope?: string
  guardrails?: string[]
  skills?: string[]
  status?: string
  published?: boolean
  preset?: string
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
  preset?: string
}

export interface AgentPreset {
  id: string
  title: string
  job: string
  layers: Array<'ontology' | 'graph' | 'semantic' | 'context'>
  tools: string[]
  guardrails: string[]
  output: string
  examples: string[]
}

export interface PreviewRequest {
  question: string
}

export interface PreviewResponse {
  answer: AgentAnswer
  evidence?: Evidence
  latency_ms?: number
  preset?: string
  answerable?: Answerable
  receipt?: Receipt
}

// ------------------------------------------------------- agent connections
export interface AgentKey {
  id: string
  prefix: string
  label: string
  created_at: string
  last_used_at: string | null
  revoked: boolean
  revoked_at?: string | null
}

export interface AgentKeysResponse {
  keys: AgentKey[]
}

/** Returned once, when a key is issued. The secret is never shown again. */
export interface IssuedKey {
  id: string
  key: string
  prefix: string
  label: string
  created_at: string
}

export interface AgentCall {
  id: string
  tool: string
  summary: string
  ok: boolean
  error: string | null
  latency_ms: number | null
  created_at: string
}

export interface AgentUsageResponse {
  calls: AgentCall[]
}

export interface AgentConnection {
  agent_id: string
  name: string
  mcp_url: string
  server_name: string
  scope: { sources: string[]; metrics: string[] }
  tools: string[]
  snippets: {
    claude_desktop: string
    cursor: string
    curl: string
    powershell: string
    claude_code: string
  }
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


// ------------------------------------------------------- context factory
export interface FactoryAssetCounts {
  total: number
  by_status: Record<string, number>
  by_kind: Record<string, number>
}

export interface FactoryConsumer {
  id: string
  name: string
  kind: string
  config?: Record<string, unknown>
}

export interface FactoryOverview {
  source: string
  quality: number
  grade: string
  assets: FactoryAssetCounts
  conflicts: number
  documents: number
  consumers: number
  consumer_list: FactoryConsumer[]
  generated_at: string
}

export interface ContextAsset {
  id: string
  kind: 'term' | 'metric' | 'relationship' | 'policy' | 'hierarchy' | string
  name: string
  description: string
  source: string
  owner: string
  status: 'draft' | 'review' | 'approved' | 'deprecated' | string
  version: number
  data: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AssetVersion {
  asset_id: string
  version: number
  snapshot: Record<string, unknown>
  status: string
  created_at: string
}

export interface FactoryAssetDetail {
  asset: ContextAsset
  versions: AssetVersion[]
}

export interface FactoryQualityDimension {
  dimension: string
  label: string
  passed: number
  total: number
  points: number
  score: number
}

export interface FactoryQualityGap {
  dimension: string
  points: number
  message: string
}

export interface FactoryQualityAsset {
  id: string
  kind: string
  name: string
  status: string
  owner: string
  score: number
  max: number
  checks: Record<string, boolean>
  gaps: FactoryQualityGap[]
}

export interface FactoryQualityReport {
  source: string
  score: number
  grade: string
  assets: FactoryQualityAsset[]
  dimensions: FactoryQualityDimension[]
  gap_count: number
  top_gaps: FactoryQualityGap[]
  generated_at: string
}

export interface FactoryConflictAsset {
  id?: string
  kind?: string
  name?: string
  status?: string
  description?: string
  owner?: string
  source?: string
  sql?: string
}

export interface FactoryConflict {
  id: string
  severity: string
  type: string
  title: string
  detail: string
  assets: FactoryConflictAsset[]
  recommendation: string
  document?: {
    id: string
    name: string
    path: string
    proposal: string
  }
}

export interface FactoryImpactNode {
  id: string
  label: string
  type: string
  kind?: string
  status?: string
  detail?: string
  relation?: string
}

export interface FactoryImpactEdge {
  source: string
  target: string
  relation: string
}

export interface FactoryImpact {
  asset: ContextAsset
  nodes: FactoryImpactNode[]
  edges: FactoryImpactEdge[]
  impacted: FactoryImpactNode[]
  summary: { total: number; agents: number; metrics: number; interfaces: number }
}

export interface FactoryDocument {
  id: string
  name: string
  path: string
  content_hash?: string
  status: string
  proposals?: Array<{ term?: string; definition?: string; origin?: string }>
  proposal_count?: number
  owner?: string
  created_at?: string
}

export interface FactoryDiscovery {
  source: string
  documents: FactoryDocument[]
  proposals: Array<{
    term: string
    definition: string
    origin: string
    document_id: string
    document_name: string
    owner: string
  }>
  total: number
}

export interface FactoryApplyResult {
  created: ContextAsset[]
  skipped: Array<{ term: string; reason: string; asset_id?: string }>
  created_count: number
  skipped_count: number
}

// --------------------------------------------- phases 4-6: ground/validate/learn
export interface GlossaryTerm {
  id: string
  kind: 'term' | 'metric' | string
  name: string
  description: string
  status: string
  owner: string
  version?: number
  synonyms: string[]
  columns: string[]
  table?: string | null
  metric_name?: string | null
  updated_at?: string
}

export interface GlossaryResponse {
  source: string
  terms: GlossaryTerm[]
}

export interface GlossaryUpdate {
  synonyms?: string[]
  columns?: string[]
  description?: string
}

export interface ValidationCheck {
  name: string
  passed: boolean
  detail: string
  severity: 'ok' | 'warning' | 'error' | string
}

export interface ValidationResult {
  status: 'pass' | 'warn' | 'fail' | string
  checks: ValidationCheck[]
  tables: string[]
  metric: string | null
  certified: { metric: string; value_expr: string; filters: string[]; measures: string[] } | null
  suggestion: string
}

export type FeedbackKind = 'wrong_number' | 'wrong_definition' | 'missing_context' | 'other' | 'proposal'

export interface FeedbackSubmit {
  source: string
  question: string
  correction: string
  kind: FeedbackKind
  answer?: string
  metric?: string | null
  agent_id?: string | null
}

export interface FeedbackItem {
  id: string
  status: string
  review_kind: string
  source: string
  question: string
  answer: string
  correction: string
  kind: FeedbackKind
  metric: string | null
  agent_id: string | null
  submitted_by?: string
  created_at: string
  /** Set on Steward proposals. */
  proposal?: { type: 'synonym'; synonym: string; metric: string } | { type: 'note'; text: string } | null
  /** Set on a decision: what was applied, if anything. */
  applied?: string | null
}

export interface MetricUsage {
  metric: string
  calls: number
  agents: number
  last_used_at: string
}
