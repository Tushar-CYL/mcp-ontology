import type {
  Agent,
  AgentConnection,
  AgentPreset,
  ContextSuggestions,
  LoadJob,
  MetricInsightsResponse,
  MetricSummary,
  AgentDraft,
  AgentKeysResponse,
  AgentUsageResponse,
  FeedbackItem,
  FeedbackSubmit,
  MetricUsage,
  ValidationResult,
  AgentsResponse,
  AskResponse,
  CertificationResponse,
  ContextQuery,
  ContextResponse,
  CreateSourceRequest,
  CreateSourceResponse,
  EvaluateMetricRequest,
  EvaluateMetricResponse,
  GraphResponse,
  HealthResponse,
  MetricHealthResponse,
  MetricsResponse,
  OntologyResponse,
  PreviewResponse,
  IssuedKey,
  RunResponse,
  SourcesResponse,
} from './types'

/**
 * Base path for the API. Relative by default so the browser never holds a
 * key or crosses an origin: the Vite dev server proxies `/api` to
 * http://127.0.0.1:8000 and a production reverse proxy does the same.
 */
const rawBase = import.meta.env.VITE_API_BASE
export const API_BASE = (typeof rawBase === 'string' && rawBase.trim()
  ? rawBase.trim()
  : '/api').replace(/\/+$/, '')

export const IS_DEV = import.meta.env.DEV

const DEFAULT_TIMEOUT_MS = 20_000
const LONG_TIMEOUT_MS = 20 * 60_000 // a cold source build can take minutes

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

interface RequestOptions {
  method?: HttpMethod
  body?: unknown
  timeoutMs?: number
  signal?: AbortSignal
  headers?: Record<string, string>
}

/** An API failure that carries the HTTP status and the server's error type. */
export class ApiError extends Error {
  readonly status: number
  readonly type: string
  readonly payload: unknown

  constructor(
    message: string,
    options: { status: number; type: string; payload?: unknown; cause?: unknown },
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.type = options.type
    this.payload = options.payload
    if (options.cause !== undefined) {
      this.cause = options.cause
    }
  }
}

function statusType(status: number): string {
  if (status === 0) return 'NetworkError'
  if (status === 400) return 'BadRequest'
  if (status === 401) return 'Unauthorized'
  if (status === 403) return 'Forbidden'
  if (status === 404) return 'NotFound'
  if (status === 409) return 'Conflict'
  if (status === 422) return 'ValidationError'
  if (status === 429) return 'TooManyRequests'
  if (status >= 500) return 'ServerError'
  return 'HttpError'
}

function statusMessage(status: number): string {
  if (status === 404) {
    return 'The API has no route for this request. This part of the service may not be available yet.'
  }
  if (status === 400 || status === 422) {
    return 'The service rejected this request. Check the values you entered and try again.'
  }
  if (status === 429) {
    return 'The service is busy. Wait a moment and try again.'
  }
  if (status >= 500) {
    return 'The service failed while answering. The detail below is its own message.'
  }
  return `The request failed with HTTP ${status}.`
}

/**
 * Turn any error body into one ApiError. Handles the documented
 * `{error:{type,message}}` envelope, a bare string body, FastAPI's `detail`,
 * and a non-JSON body. Exported so the error rendering itself is testable.
 */
export function normalizeApiError(status: number, payload: unknown): ApiError {
  const fallback = statusMessage(status)

  if (payload !== null && typeof payload === 'object') {
    const record = payload as Record<string, unknown>
    const envelope = record.error
    if (envelope !== null && typeof envelope === 'object') {
      const detail = envelope as Record<string, unknown>
      const message =
        typeof detail.message === 'string' && detail.message.trim()
          ? detail.message.trim()
          : fallback
      const type =
        typeof detail.type === 'string' && detail.type.trim()
          ? detail.type.trim()
          : statusType(status)
      return new ApiError(message, { status, type, payload })
    }
    if (typeof envelope === 'string' && envelope.trim()) {
      return new ApiError(envelope.trim(), { status, type: statusType(status), payload })
    }
    if (typeof record.message === 'string' && record.message.trim()) {
      return new ApiError(record.message.trim(), { status, type: statusType(status), payload })
    }
    if (typeof record.detail === 'string' && record.detail.trim()) {
      return new ApiError(record.detail.trim(), { status, type: statusType(status), payload })
    }
  }

  if (typeof payload === 'string' && payload.trim()) {
    return new ApiError(payload.trim(), { status, type: statusType(status), payload })
  }

  return new ApiError(fallback, { status, type: statusType(status), payload })
}

/** True when the caller cancelled the request (not a timeout or a failure). */
export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

export interface ErrorDescription {
  title: string
  message: string
  type: string
  status: number
  hint?: string
}

/** Human-readable rendering for any thrown value, used by ErrorState. */
export function describeError(error: unknown): ErrorDescription {
  if (error instanceof ApiError) {
    const title =
      error.status === 404
        ? 'Not available yet'
        : error.status === 0
          ? 'Cannot reach the service'
          : error.status >= 500
            ? 'The service failed'
            : 'That request was rejected'

    let hint: string | undefined
    if (error.status === 0) {
      hint = 'Start the local API (python -m api.http) and check that /api is proxied to it.'
    } else if (error.status === 404) {
      hint = 'No fallback data was invented. This screen stays empty until the endpoint answers.'
    } else if (error.status >= 500) {
      hint = 'Nothing was retried automatically. Retry once, then check the API console.'
    }

    return { title, message: error.message, type: error.type, status: error.status, hint }
  }

  if (error instanceof Error) {
    return {
      title: 'Something went wrong',
      message: error.message || 'An unexpected error occurred.',
      type: error.name,
      status: 0,
    }
  }

  return {
    title: 'Something went wrong',
    message: typeof error === 'string' ? error : 'An unexpected error occurred.',
    type: 'Unknown',
    status: 0,
  }
}

export type QueryValue = string | number | boolean | null | undefined

/** Build a query string, dropping empty values. */
export function queryString(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

/** One typed fetch wrapper: JSON in, JSON out, a timeout, real errors. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = 'GET',
    body,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal,
    headers = {},
  } = options

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const forwardAbort = () => controller.abort(signal?.reason)
  if (signal) {
    if (signal.aborted) controller.abort(signal.reason)
    else signal.addEventListener('abort', forwardAbort, { once: true })
  }

  const hasBody = body !== undefined

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        Accept: 'application/json',
        ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      body: hasBody ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      credentials: 'same-origin',
      cache: 'no-store',
    })

    const text = await response.text()
    let payload: unknown
    if (text.trim()) {
      try {
        payload = JSON.parse(text) as unknown
      } catch {
        payload = text
      }
    }

    if (!response.ok) {
      throw normalizeApiError(response.status, payload)
    }

    return (payload ?? undefined) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (signal?.aborted) throw error // the caller cancelled; not an error state
    if (timedOut) {
      throw new ApiError(
        `The request took longer than ${Math.round(timeoutMs / 1000)} seconds. The server may still be working — retry, or give it more time.`,
        { status: 0, type: 'TimeoutError', cause: error },
      )
    }
    if (isAbortError(error)) {
      throw new ApiError('The request was cancelled.', {
        status: 0,
        type: 'AbortError',
        cause: error,
      })
    }
    throw new ApiError(
      'Could not reach the local API. Check that the service is running and that /api is proxied to it.',
      { status: 0, type: 'NetworkError', cause: error },
    )
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forwardAbort)
  }
}

/** The one place that knows every endpoint path. */
export const api = {
  health: (signal?: AbortSignal) =>
    request<HealthResponse>('/health', { signal, timeoutMs: 8_000 }),

  listSources: (signal?: AbortSignal) =>
    request<SourcesResponse>('/sources', { signal, timeoutMs: 15_000 }),

  createSource: (payload: CreateSourceRequest, signal?: AbortSignal) =>
    request<CreateSourceResponse>('/sources', {
      method: 'POST',
      body: payload,
      signal,
      timeoutMs: LONG_TIMEOUT_MS,
    }),

  ontology: (source: string, signal?: AbortSignal) =>
    request<OntologyResponse>(`/layers/ontology${queryString({ source })}`, { signal }),

  graph: (source: string, limit: number, signal?: AbortSignal) =>
    request<GraphResponse>(`/layers/graph${queryString({ source, limit })}`, {
      signal,
      timeoutMs: 45_000,
    }),

  subgraph: (source: string, limit: number, relation?: string, signal?: AbortSignal) =>
    request<GraphResponse>(
      `/graph/subgraph${queryString({ source, limit, relation })}`,
      { signal, timeoutMs: 45_000 },
    ),

  metrics: (source: string, signal?: AbortSignal) =>
    request<MetricsResponse>(`/metrics${queryString({ source })}`, { signal }),

  evaluateMetric: (name: string, payload: EvaluateMetricRequest, signal?: AbortSignal) =>
    request<EvaluateMetricResponse>(`/metrics/${encodeURIComponent(name)}/evaluate`, {
      method: 'POST',
      body: payload,
      signal,
      timeoutMs: 90_000,
    }),

  metricHealth: (name: string, source: string, signal?: AbortSignal) =>
    request<MetricHealthResponse>(
      `/metrics/${encodeURIComponent(name)}/health${queryString({ source })}`,
      { signal, timeoutMs: 60_000 },
    ),

  context: (query: ContextQuery, signal?: AbortSignal) =>
    request<ContextResponse>(`/context${queryString({ ...query })}`, {
      signal,
      timeoutMs: 30_000,
    }),

  /** Cached per source on the server; `refresh` re-runs every check, which
   * scans the whole graph and can take minutes on large sources. */
  certification: (source: string, signal?: AbortSignal, refresh = false) =>
    request<CertificationResponse>(
      `/certification${queryString({ source, refresh: refresh ? 'true' : undefined })}`,
      { signal, timeoutMs: 300_000 },
    ),

  agents: (signal?: AbortSignal) =>
    request<AgentsResponse>('/agents', { signal, timeoutMs: 15_000 }),

  createAgent: (draft: AgentDraft, signal?: AbortSignal) =>
    request<Agent>('/agents', { method: 'POST', body: draft, signal, timeoutMs: 30_000 }),

  updateAgent: (id: string, draft: AgentDraft, signal?: AbortSignal) =>
    request<Agent>(`/agents/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: draft,
      signal,
      timeoutMs: 30_000,
    }),

  previewAgent: (id: string, question: string, signal?: AbortSignal) =>
    request<PreviewResponse>(`/agents/${encodeURIComponent(id)}/preview`, {
      method: 'POST',
      body: { question },
      signal,
      timeoutMs: 180_000,
    }),

  askAgent: (id: string, question: string, signal?: AbortSignal) =>
    request<AskResponse>(`/agents/${encodeURIComponent(id)}/ask`, {
      method: 'POST',
      body: { question },
      signal,
      timeoutMs: 180_000,
    }),

  deleteAgent: (id: string, signal?: AbortSignal) =>
    request<{ deleted: string }>(`/agents/${encodeURIComponent(id)}`, {
      method: 'DELETE', signal, timeoutMs: 15_000,
    }),

  agentKeys: (id: string, signal?: AbortSignal) =>
    request<AgentKeysResponse>(`/agents/${encodeURIComponent(id)}/keys`, {
      signal, timeoutMs: 15_000,
    }),

  issueAgentKey: (id: string, label: string, signal?: AbortSignal) =>
    request<IssuedKey>(`/agents/${encodeURIComponent(id)}/keys`, {
      method: 'POST', body: { label }, signal, timeoutMs: 15_000,
    }),

  revokeAgentKey: (id: string, keyId: string, signal?: AbortSignal) =>
    request<{ revoked: string }>(
      `/agents/${encodeURIComponent(id)}/keys/${encodeURIComponent(keyId)}`,
      { method: 'DELETE', signal, timeoutMs: 15_000 },
    ),

  agentUsage: (id: string, signal?: AbortSignal) =>
    request<AgentUsageResponse>(`/agents/${encodeURIComponent(id)}/usage`, {
      signal, timeoutMs: 15_000,
    }),

  agentConnection: (id: string, signal?: AbortSignal) =>
    request<AgentConnection>(`/agents/${encodeURIComponent(id)}/connection`, {
      signal, timeoutMs: 15_000,
    }),

  // ------------------------------------------------ phase 5: validate
  validateSql: (payload: { source: string; sql: string; metric?: string }, signal?: AbortSignal) =>
    request<ValidationResult>('/validate/sql', {
      method: 'POST', body: payload, signal, timeoutMs: 60_000,
    }),

  // ------------------------------------------------ phase 6: learn
  submitFeedback: (payload: FeedbackSubmit, signal?: AbortSignal) =>
    request<FeedbackItem>('/feedback', { method: 'POST', body: payload, signal, timeoutMs: 20_000 }),

  feedback: (source: string, pendingOnly = false, signal?: AbortSignal) =>
    request<{ items: FeedbackItem[] }>(
      `/feedback${queryString({ source, pending: pendingOnly ? 'true' : undefined })}`,
      { signal, timeoutMs: 20_000 },
    ),

  decideFeedback: (id: string, decision: 'approved' | 'rejected', note = '', signal?: AbortSignal) =>
    request<FeedbackItem>(`/feedback/${encodeURIComponent(id)}/decision`, {
      method: 'POST', body: { decision, note }, signal, timeoutMs: 20_000,
    }),

  metricUsage: (source: string, signal?: AbortSignal) =>
    request<{ source: string; metrics: MetricUsage[] }>(
      `/usage/metrics${queryString({ source })}`, { signal, timeoutMs: 20_000 },
    ),

  // ------------------------------------------------ agents: presets
  agentPresets: (signal?: AbortSignal) =>
    request<{ presets: AgentPreset[] }>('/agent-presets', { signal, timeoutMs: 15_000 }),

  // ------------------------------------------------ semantic: autopilot
  setMetricStatus: (name: string, source: string, status: 'approved' | 'draft' | 'deprecated',
    signal?: AbortSignal) =>
    request<MetricSummary>(`/metrics/${encodeURIComponent(name)}/status`, {
      method: 'POST', body: { source, status }, signal, timeoutMs: 15_000,
    }),

  approveProposedMetrics: (source: string, signal?: AbortSignal) =>
    request<{ source: string; approved: string[] }>('/metrics/approve-proposed', {
      method: 'POST', body: { source }, signal, timeoutMs: 30_000,
    }),

  metricInsights: (
    name: string,
    query: { source: string; groupBy?: string; previewDraft?: boolean; grain?: string },
    signal?: AbortSignal,
  ) =>
    request<MetricInsightsResponse>(
      `/metrics/${encodeURIComponent(name)}/insights${queryString({
        source: query.source,
        group_by: query.groupBy || undefined,
        preview_draft: query.previewDraft ? 'true' : undefined,
        grain: query.grain || undefined,
      })}`,
      { signal, timeoutMs: 120_000 },
    ),

  /** Load a source in the background; poll `job` for progress. */
  startSourceLoad: (payload: CreateSourceRequest, signal?: AbortSignal) =>
    request<{ job_id: string; status: string }>('/sources', {
      method: 'POST', body: { ...payload, background: true }, signal, timeoutMs: 30_000,
    }),

  job: (jobId: string, signal?: AbortSignal) =>
    request<LoadJob>(`/jobs/${encodeURIComponent(jobId)}`, { signal, timeoutMs: 15_000 }),

  entities: (source: string, cls: string, q = '', signal?: AbortSignal) =>
    request<{ source: string; class: string; keys: string[]; total: number }>(
      `/entities${queryString({ source, class: cls, q: q || undefined, limit: 50 })}`,
      { signal, timeoutMs: 30_000 },
    ),

  contextSuggestions: (source: string, signal?: AbortSignal) =>
    request<ContextSuggestions>(`/context/suggestions${queryString({ source })}`, {
      signal, timeoutMs: 60_000,
    }),

  // ------------------------------------------------ semantic: synonyms
  setMetricSynonyms: (name: string, source: string, synonyms: string[], signal?: AbortSignal) =>
    request<{ metric: string; source: string; synonyms: string[] }>(
      `/metrics/${encodeURIComponent(name)}/synonyms`,
      { method: 'PUT', body: { source, synonyms }, signal, timeoutMs: 15_000 },
    ),

  getRun: (runId: string, signal?: AbortSignal) =>
    request<RunResponse>(`/runs/${encodeURIComponent(runId)}`, { signal, timeoutMs: 30_000 }),
}
