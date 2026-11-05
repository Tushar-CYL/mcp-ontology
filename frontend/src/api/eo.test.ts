import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

type Call = { url: string; method: string; body: unknown }

function stubFetch(payload: unknown, status = 200): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, method: init.method ?? 'GET',
      body: init.body ? JSON.parse(String(init.body)) : undefined })
    return new Response(JSON.stringify(payload), { status })
  }))
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('ontology accelerator client', () => {
  it('starts the demo as a background job', async () => {
    const calls = stubFetch({ job_id: 'job_1', status: 'running' })
    const out = await api.eoDemo(120)
    expect(out.job_id).toBe('job_1')
    expect(calls[0]).toMatchObject({ method: 'POST', body: { customers: 120, run: true } })
    expect(calls[0].url).toMatch(/\/eo\/demo$/)
  })

  it('reads the journey state of an ontology, encoding its id', async () => {
    const calls = stubFetch({ steps: [] })
    await api.eoState('sales 2024')
    expect(calls[0].url).toMatch(/\/eo\/sales%202024$/)
  })

  it('asks for items of one kind', async () => {
    const calls = stubFetch({ items: [] })
    await api.eoItems('sales', 'mapping')
    expect(calls[0].url).toMatch(/\/eo\/sales\/items\?kind=mapping$/)
  })

  it('sends a decision with who made it', async () => {
    const calls = stubFetch({ status: 'approved' })
    await api.eoDecide('sales', { kind: 'concept', key: 'Customer', decision: 'approved', by: 'ana' })
    expect(calls[0].body).toEqual({ kind: 'concept', key: 'Customer', decision: 'approved', by: 'ana' })
  })

  it('bulk-approves above a confidence', async () => {
    const calls = stubFetch({ approved: ['a'] })
    await api.eoApproveAll('sales', 'mapping', 'ana', 0.9)
    expect(calls[0].body).toEqual({ kind: 'mapping', by: 'ana', min_confidence: 0.9 })
  })

  it('publishes, diffs and checks drift', async () => {
    const calls = stubFetch({})
    await api.eoPublish('sales', 'ana', 'v1')
    await api.eoDiff('sales', 1, 2)
    await api.eoDrift('sales')
    expect(calls[0]).toMatchObject({ method: 'POST', body: { by: 'ana', notes: 'v1' } })
    expect(calls[1].url).toMatch(/\/eo\/sales\/diff\?a=1&b=2$/)
    expect(calls[2]).toMatchObject({ method: 'POST' })
    expect(calls[2].url).toMatch(/\/eo\/sales\/drift$/)
  })

  it('resolves an entity from any id', async () => {
    const calls = stubFetch({ entity_id: 'M1' })
    await api.eoResolve('sales', 'B-5000')
    expect(calls[0].url).toMatch(/\/eo\/sales\/resolve\?value=B-5000$/)
  })

  it('builds download links without fetching', () => {
    expect(api.eoExportUrl('sales', 'zip')).toMatch(/\/eo\/sales\/export\/zip$/)
    expect(api.eoExportUrl('sales', 'turtle', 2)).toMatch(/export\/turtle\?version=2$/)
  })

  it('surfaces the server error message', async () => {
    stubFetch({ error: { type: 'Forbidden', message: "'bob' is not an approver" } }, 403)
    await expect(api.eoApproveAll('sales', 'concept', 'bob')).rejects.toMatchObject({
      status: 403, message: "'bob' is not an approver" })
  })
})
