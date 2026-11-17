import { describe, expect, it } from 'vitest'
import { downloadError, fileName } from './download'

describe('downloads', () => {
  it('saves under the name the server gives', () => {
    expect(fileName('attachment; filename="strata-semantic.zip"', 'x.zip')).toBe('strata-semantic.zip')
    expect(fileName("attachment; filename*=UTF-8''olist%20model.json", 'x')).toBe('olist model.json')
    expect(fileName(null, 'fallback.json')).toBe('fallback.json')
  })

  it('turns an older server into an instruction, not a file', () => {
    const body = { error: { type: 'NotFound', message: 'this server has no route GET /api/bundle. If the web app offers it, the server is running an older version' } }
    expect(downloadError(404, body)).toMatch(/start it again with python run_server.py/)
  })

  it('says any other error as the server said it', () => {
    expect(downloadError(404, { error: { message: "no ontology 'nope'" } })).toBe("no ontology 'nope'")
    expect(downloadError(500, null)).toBe('the server answered 500')
  })
})
