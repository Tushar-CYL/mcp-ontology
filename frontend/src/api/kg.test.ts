import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

function stubFetch(payload: unknown, status = 200): string[] {
  const urls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    urls.push(url)
    return new Response(JSON.stringify(payload), { status })
  }))
  return urls
}

afterEach(() => vi.unstubAllGlobals())

describe('knowledge graph client', () => {
  it('searches with the query encoded', async () => {
    const urls = stubFetch({ query: 'a&b', results: [] })
    await api.kgSearch('shop', 'a&b c')
    expect(urls[0]).toMatch(/\/kg\/shop\/search\?q=a%26b\+c$/)
  })

  it('opens an entity whose key holds a separator', async () => {
    const urls = stubFetch({ set: 'shop.order_line', key: '1|SKU002', fields: [], connections: [] })
    await api.kgEntity('shop', 'shop.order_line', '1|SKU002')
    expect(urls[0]).toContain('set=shop.order_line')
    expect(urls[0]).toContain('key=1%7CSKU002')
  })

  it('asks for a path between two entities', async () => {
    const urls = stubFetch({ found: false, text: 'No connection within 3 steps' })
    const out = await api.kgPath('shop', { set: 'shop.customer', key: '2' }, { set: 'graph:kb', key: 'https://kb.org/x' }, 3)
    expect(out.found).toBe(false)
    expect(urls[0]).toContain('from_set=shop.customer')
    expect(urls[0]).toContain('to_set=graph%3Akb')
    expect(urls[0]).toContain('to_key=https%3A%2F%2Fkb.org%2Fx')
    expect(urls[0]).toContain('max_hops=3')
  })

  it('links the Neo4j download to the API', () => {
    expect(api.kgNeo4jUrl('my shop')).toMatch(/\/kg\/my%20shop\/neo4j$/)
  })

  it('passes a plain graph error through', async () => {
    stubFetch({ error: { type: 'GraphError', message: 'type an id or a name to search for' } }, 400)
    await expect(api.kgSearch('shop', ' ')).rejects.toThrow('type an id or a name')
  })
})

describe('older server', () => {
  it('keeps the "no route" message so the page can say "restart"', async () => {
    stubFetch({ error: { type: 'NotFound', message: 'this server has no route GET /api/kg/x/overview. If the web app offers it, the server is running an older version' } }, 404)
    await expect(api.kgOverview('x')).rejects.toMatchObject({ status: 404, message: expect.stringMatching(/no route/) })
  })
})
