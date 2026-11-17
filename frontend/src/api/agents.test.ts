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

describe('agents of an ontology', () => {
  it('lists the built-ins and yours for one ontology', async () => {
    const calls = stubFetch({ ontology: 'olist', builtin: [], mine: [], kinds: [], things: [], metrics: [] })
    await api.ontoAgents('olist')
    expect(calls[0].url).toMatch(/\/onto-agents\/olist$/)
  })

  it('encodes agent ids, which contain colons', async () => {
    const calls = stubFetch({ id: 'agent:olist:mine' })
    await api.copyOntoAgent('builtin:olist:metric')
    expect(calls[0]).toMatchObject({ method: 'POST', body: {} })
    expect(calls[0].url).toMatch(/\/oagents\/builtin%3Aolist%3Ametric\/copy$/)
    await api.askOntoAgent('agent:olist:mine', 'How many orders?')
    expect(calls[1]).toMatchObject({ method: 'POST', body: { question: 'How many orders?' } })
    expect(calls[1].url).toMatch(/\/oagents\/agent%3Aolist%3Amine\/ask$/)
  })

  it('creates, changes and tries an agent with its scope', async () => {
    const calls = stubFetch({ id: 'agent:o:x' })
    const body = { name: 'Lines', kind: 'insight' as const, scope: { things: ['Order Item'], metrics: [] } }
    await api.createOntoAgent('o', body)
    expect(calls[0]).toMatchObject({ method: 'POST', body })
    await api.updateOntoAgent('agent:o:x', { instructions: 'Be brief.' })
    expect(calls[1]).toMatchObject({ method: 'PUT', body: { instructions: 'Be brief.' } })
    await api.tryOntoAgent('o', { ...body, question: 'q?' })
    expect(calls[2].url).toMatch(/\/onto-agents\/o\/try$/)
    expect(calls[2].body).toMatchObject({ question: 'q?', kind: 'insight' })
  })

  it('says a built-in cannot be changed', async () => {
    stubFetch({ error: { type: 'ReadOnly', message: 'built-in agents are not changed: make a copy' } }, 403)
    await expect(api.updateOntoAgent('builtin:o:guide', { name: 'x' })).rejects.toThrow(/make a copy/)
  })
})
