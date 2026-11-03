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

describe('agent connection client', () => {
  it('issues a key with a label', async () => {
    const calls = stubFetch({ id: 'key_1', key: 'strata_x', prefix: 'strata_x' })
    const issued = await api.issueAgentKey('agent 1', 'cursor')
    expect(issued.key).toBe('strata_x')
    expect(calls[0].method).toBe('POST')
    expect(calls[0].url).toMatch(/\/agents\/agent%201\/keys$/)
    expect(calls[0].body).toEqual({ label: 'cursor' })
  })

  it('lists keys, usage and connection details', async () => {
    const calls = stubFetch({ keys: [], calls: [], snippets: {} })
    await api.agentKeys('a1')
    await api.agentUsage('a1')
    await api.agentConnection('a1')
    expect(calls.map((c) => c.url.replace(/^.*\/agents/, ''))).toEqual([
      '/a1/keys', '/a1/usage', '/a1/connection',
    ])
  })

  it('revokes a key with DELETE', async () => {
    const calls = stubFetch({ revoked: 'key_1' })
    await api.revokeAgentKey('a1', 'key_1')
    expect(calls[0].method).toBe('DELETE')
    expect(calls[0].url).toMatch(/\/agents\/a1\/keys\/key_1$/)
  })

  it('asks for cached certification unless a refresh is forced', async () => {
    const calls = stubFetch({ layers: [], cached: true })
    await api.certification('revenue')
    await api.certification('revenue', undefined, true)
    expect(calls[0].url).toMatch(/certification\?source=revenue$/)
    expect(calls[1].url).toMatch(/certification\?source=revenue&refresh=true$/)
  })

  it('no longer offers publishing or custom skills', () => {
    expect('publishAgent' in api).toBe(false)
    expect('createSkill' in api).toBe(false)
    expect('deleteSkill' in api).toBe(false)
  })
})
