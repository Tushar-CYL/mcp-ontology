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

describe('presets and synonyms client', () => {
  it('lists agent presets', async () => {
    const calls = stubFetch({ presets: [] })
    await api.agentPresets()
    expect(calls[0].url).toMatch(/\/agent-presets$/)
  })

  it('saves metric synonyms with the source', async () => {
    const calls = stubFetch({ synonyms: ['sales'] })
    await api.setMetricSynonyms('revenue', 'shop', ['sales'])
    expect(calls[0].method).toBe('PUT')
    expect(calls[0].url).toMatch(/\/metrics\/revenue\/synonyms$/)
    expect(calls[0].body).toEqual({ source: 'shop', synonyms: ['sales'] })
  })

  it('creates an agent with its preset', async () => {
    const calls = stubFetch({ id: 'a1', preset: 'metric' })
    await api.createAgent({
      name: 'm', purpose: '', problem_statement: '', instructions: 'x',
      sources: ['shop'], metrics: ['revenue'], guardrails: [], skills: [], preset: 'metric',
    })
    expect((calls[0].body as { preset: string }).preset).toBe('metric')
  })

  it('no longer offers the removed screens', () => {
    for (const gone of ['factoryOverview', 'factoryAssets', 'glossary', 'updateGlossaryTerm',
      'sourceGuardrails', 'saveSourceGuardrails', 'suggestGuardrails', 'skills', 'tools']) {
      expect(gone in api).toBe(false)
    }
  })
})
