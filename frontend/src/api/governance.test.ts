import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

type Call = { url: string; method: string; body: unknown }

function stubFetch(payload: unknown): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push({
      url,
      method: init.method ?? 'GET',
      body: init.body ? JSON.parse(String(init.body)) : undefined,
    })
    return new Response(JSON.stringify(payload), { status: 200 })
  }))
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('validate client (phase 5)', () => {
  it('posts the SQL with its source and metric', async () => {
    const calls = stubFetch({ status: 'pass', checks: [] })
    await api.validateSql({ source: 'revenue', metric: 'revenue', sql: 'SELECT 1' })
    expect(calls[0].method).toBe('POST')
    expect(calls[0].url).toMatch(/\/validate\/sql$/)
    expect(calls[0].body).toEqual({ source: 'revenue', metric: 'revenue', sql: 'SELECT 1' })
  })
})

describe('feedback and usage client (phase 6)', () => {
  it('submits, lists pending and decides', async () => {
    const calls = stubFetch({ items: [] })
    await api.submitFeedback({
      source: 'revenue', question: 'q', correction: 'c', kind: 'wrong_number',
    })
    await api.feedback('revenue', true)
    await api.decideFeedback('fb1', 'approved', 'ok')
    expect(calls.map((c) => `${c.method} ${c.url.replace(/^.*\/api/, '')}`)).toEqual([
      'POST /feedback',
      'GET /feedback?source=revenue&pending=true',
      'POST /feedback/fb1/decision',
    ])
    expect(calls[2].body).toEqual({ decision: 'approved', note: 'ok' })
  })

  it('reads metric usage for a source', async () => {
    const calls = stubFetch({ metrics: [] })
    await api.metricUsage('revenue')
    expect(calls[0].url).toMatch(/\/usage\/metrics\?source=revenue$/)
  })
})
