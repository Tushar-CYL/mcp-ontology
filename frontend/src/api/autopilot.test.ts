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

describe('semantic autopilot client', () => {
  it('approves one metric', async () => {
    const calls = stubFetch({ name: 'x', status: 'approved' })
    await api.setMetricStatus('sales_documents_count', 'salt', 'approved')
    expect(calls[0].method).toBe('POST')
    expect(calls[0].url).toMatch(/\/metrics\/sales_documents_count\/status$/)
    expect(calls[0].body).toEqual({ source: 'salt', status: 'approved' })
  })

  it('approves every proposal for a source', async () => {
    const calls = stubFetch({ approved: [] })
    await api.approveProposedMetrics('salt')
    expect(calls[0].url).toMatch(/\/metrics\/approve-proposed$/)
    expect(calls[0].body).toEqual({ source: 'salt' })
  })

  it('reads insights, previewing drafts when asked', async () => {
    const calls = stubFetch({ trend: [], contributors: [] })
    await api.metricInsights('m', { source: 'salt', previewDraft: true })
    await api.metricInsights('m', { source: 'salt' })
    expect(calls[0].url).toMatch(/\/metrics\/m\/insights\?source=salt&preview_draft=true$/)
    expect(calls[1].url).toMatch(/\/metrics\/m\/insights\?source=salt$/)
  })
})

describe('context suggestions client', () => {
  it('asks for questions built from this source', async () => {
    const calls = stubFetch({ questions: [], note: '' })
    await api.contextSuggestions('salt')
    expect(calls[0].url).toMatch(/\/context\/suggestions\?source=salt$/)
  })
})

describe('entity search client', () => {
  it('asks the graph for keys of one kind, with search', async () => {
    const calls = stubFetch({ keys: [], total: 0 })
    await api.entities('salt', 'Customer', 'A1')
    await api.entities('salt', 'Customer')
    expect(calls[0].url).toMatch(/\/entities\?source=salt&class=Customer&q=A1&limit=50$/)
    expect(calls[1].url).toMatch(/\/entities\?source=salt&class=Customer&limit=50$/)
  })
})

describe('background loading client', () => {
  it('starts a background load and reads its job', async () => {
    const calls = stubFetch({ job_id: 'job_1', status: 'running' })
    const started = await api.startSourceLoad({ path: 'C:/data/salt', name: 'salt' })
    await api.job(started.job_id)
    expect(calls[0].method).toBe('POST')
    expect(calls[0].url).toMatch(/\/sources$/)
    expect(calls[0].body).toEqual({ path: 'C:/data/salt', name: 'salt', background: true })
    expect(calls[1].url).toMatch(/\/jobs\/job_1$/)
  })

  it('asks for a trend at a chosen grain', async () => {
    const calls = stubFetch({ trend: [] })
    await api.metricInsights('m', { source: 'salt', grain: 'quarter' })
    expect(calls[0].url).toMatch(/insights\?source=salt&grain=quarter$/)
  })
})
