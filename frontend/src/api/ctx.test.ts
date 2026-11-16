import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

type Call = { url: string; method: string; body: unknown }

function stubFetch(payload: unknown, status = 200): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, method: init.method ?? 'GET', body: init.body ? JSON.parse(String(init.body)) : undefined })
    return new Response(JSON.stringify(payload), { status })
  }))
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('context client', () => {
  it('builds context for a question with a size budget', async () => {
    const calls = stubFetch({ question: 'q', context: '[1] x', steps: {} })
    await api.ctxBuild('my shop', 'What did customer 17 order?', 800)
    expect(calls[0]).toMatchObject({ method: 'POST', body: { question: 'What did customer 17 order?', budget_chars: 800 } })
    expect(calls[0].url).toMatch(/\/ctx\/my%20shop\/build$/)
  })

  it('sends feedback with the question it is about', async () => {
    const calls = stubFetch({ saved: true, changes: [], reply: 'noted' })
    const out = await api.ctxFeedback('shop', 'q?', 'cancelled orders do not count')
    expect(out.saved).toBe(true)
    expect(calls[0]).toMatchObject({ method: 'POST', body: { question: 'q?', text: 'cancelled orders do not count' } })
  })

  it('passes a plain context error through', async () => {
    stubFetch({ error: { type: 'ContextError', message: 'type a question first' } }, 400)
    await expect(api.ctxBuild('shop', ' ')).rejects.toThrow('type a question first')
  })
})
