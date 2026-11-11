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

describe('simple ontology client', () => {
  it('starts a build with sources, paths and metadata', async () => {
    const calls = stubFetch({ job_id: 'job_9', status: 'running' })
    const out = await api.ontoBuild({ name: 'Plant', sources: ['iot'],
      paths: [{ path: 'D:/data/x.csv' }], metadata: ['model.bim'], domain: 'IoT' })
    expect(out.job_id).toBe('job_9')
    expect(calls[0]).toMatchObject({ method: 'POST', body: { name: 'Plant', sources: ['iot'],
      paths: [{ path: 'D:/data/x.csv' }], metadata: ['model.bim'] } })
    expect(calls[0].url).toMatch(/\/onto\/build$/)
  })

  it('encodes the ontology id', async () => {
    const calls = stubFetch({ things: [] })
    await api.ontoView('my plant')
    expect(calls[0].url).toMatch(/\/onto\/my%20plant$/)
  })

  it('sends a context note and a field edit', async () => {
    const calls = stubFetch({ changes: [], reply: 'ok', method: 'rules', version: null })
    await api.ontoContext('p', 'KUNNR = customer number')
    expect(calls[0]).toMatchObject({ method: 'POST', body: { text: 'KUNNR = customer number' } })
    await api.ontoEditField('p', { key: 'iot.r.temp', label: 'Temperature', unit: '°C' })
    expect(calls[1]).toMatchObject({ method: 'PUT',
      body: { key: 'iot.r.temp', label: 'Temperature', unit: '°C' } })
    expect(calls[1].url).toMatch(/\/onto\/p\/fields$/)
  })

  it('renames a thing, rebuilds, deletes', async () => {
    const calls = stubFetch({})
    await api.ontoEditThing('p', { key: 'Reading', name: 'Sensor reading' })
    await api.ontoRebuild('p')
    await api.ontoDelete('p')
    expect(calls.map((c) => `${c.method} ${c.url.replace(/^.*\/onto/, '')}`)).toEqual([
      'PUT /p/things', 'POST /p/rebuild', 'DELETE /p'])
  })

  it('surfaces the server error message', async () => {
    stubFetch({ error: { type: 'BadRequest', message: 'these sources are not loaded: x' } }, 400)
    await expect(api.ontoBuild({ name: 'x', sources: ['x'], paths: [], metadata: [] }))
      .rejects.toThrow('these sources are not loaded: x')
  })

  it('says the server cannot be reached when the proxy answers 502', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 502 })))
    await expect(api.ontoList()).rejects.toMatchObject({ type: 'Unreachable' })
    await expect(api.ontoList()).rejects.toThrow('Cannot reach the Strata server')
  })

  it('keeps the server message when the API itself answers 503', async () => {
    stubFetch({ error: { type: 'Busy', message: 'warming up' } }, 503)
    await expect(api.ontoList()).rejects.toThrow('warming up')
  })

  it('explains a 405 as an older server (the web app is newer than the API)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('Method Not Allowed', { status: 405 })))
    await expect(api.ontoAsk('p', 'how many?')).rejects.toThrow('older version')
  })

  it('builds the Excel download link', () => {
    expect(api.ontoExcelUrl('my plant')).toMatch(/\/onto\/my%20plant\/excel$/)
  })
})
