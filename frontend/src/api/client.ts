import type {
  Agent,
  AgentDraft,
  AgentsResponse,
  AskResponse,
  CertificationResponse,
  CreateSkillRequest,
  GuardrailSuggestResponse,
  SourceGuardrailsResponse,
  SkillDefinition,
  SkillsResponse,
  ContextQuery,
  ContextResponse,
  CreateSourceRequest,
  CreateSourceResponse,
  EvaluateMetricRequest,
  EvaluateMetricResponse,
  GraphResponse,
  HealthResponse,
  MetricsResponse,
  OntologyResponse,
  PreviewResponse,
  PublishResponse,
  RunResponse,
  SourcesResponse,
  ToolsResponse,
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

  context: (query: ContextQuery, signal?: AbortSignal) =>
    request<ContextResponse>(`/context${queryString({ ...query })}`, {
      signal,
      timeoutMs: 30_000,
    }),

  tools: (signal?: AbortSignal) =>
    request<ToolsResponse>('/tools', { signal, timeoutMs: 15_000 }),

  skills: (source: string, signal?: AbortSignal) =>
    request<SkillsResponse>(`/skills${queryString({ source })}`, { signal }),

  createSkill: (payload: CreateSkillRequest, signal?: AbortSignal) =>
    request<SkillDefinition>('/skills', {
      method: 'POST', body: payload, signal, timeoutMs: 30_000,
    }),

  deleteSkill: (id: string, signal?: AbortSignal) =>
    request<{ deleted: string }>(`/skills/${encodeURIComponent(id)}`, {
      method: 'DELETE', signal, timeoutMs: 15_000,
    }),

  sourceGuardrails: (source: string, signal?: AbortSignal) =>
    request<SourceGuardrailsResponse>(
      `/sources/${encodeURIComponent(source)}/guardrails`,
      { signal, timeoutMs: 15_000 },
    ),

  saveSourceGuardrails: (
    source: string,
    rules: Array<string | { instruction: string; label?: string }>,
    signal?: AbortSignal,
  ) =>
    request<SourceGuardrailsResponse>(
      `/sources/${encodeURIComponent(source)}/guardrails`,
      { method: 'PUT', body: { rules }, signal, timeoutMs: 30_000 },
    ),

  certification: (source: string, signal?: AbortSignal) =>
    request<CertificationResponse>(`/certification${queryString({ source })}`, {
      signal, timeoutMs: 45_000,
    }),

  suggestGuardrails: (
    payload: { problem_statement: string; source_id?: string; metrics?: string[] },
    signal?: AbortSignal,
  ) =>
    request<GuardrailSuggestResponse>('/agents/suggest-guardrails', {
      method: 'POST', body: payload, signal, timeoutMs: 90_000,
    }),

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

  publishAgent: (id: string, signal?: AbortSignal) =>
    request<PublishResponse>(`/agents/${encodeURIComponent(id)}/publish`, {
      method: 'POST',
      body: {},
      signal,
      timeoutMs: 45_000,
    }),

  askAgent: (id: string, question: string, signal?: AbortSignal) =>
    request<AskResponse>(`/agents/${encodeURIComponent(id)}/ask`, {
      method: 'POST',
      body: { question },
      signal,
      timeoutMs: 180_000,
    }),

  getRun: (runId: string, signal?: AbortSignal) =>
    request<RunResponse>(`/runs/${encodeURIComponent(runId)}`, { signal, timeoutMs: 30_000 }),
}
