import { describe, expect, it } from 'vitest'
import { normalizeApiError } from './client'

describe('normalizeApiError', () => {
  it('reads the service envelope', () => {
    const error = normalizeApiError(404, {
      error: { type: 'MetricError', message: 'no approved metric "profit"' },
    })
    expect(error.status).toBe(404)
    expect(error.type).toBe('MetricError')
    expect(error.message).toContain('profit')
  })

  it('falls back to a readable message for a bare body', () => {
    const error = normalizeApiError(500, 'upstream exploded')
    expect(error.status).toBe(500)
    expect(error.type).toBe('ServerError')
    expect(error.message).toContain('upstream exploded')
  })

  it('handles an empty response', () => {
    const error = normalizeApiError(0, null)
    expect(error.type).toBe('NetworkError')
    expect(error.message.length).toBeGreaterThan(0)
  })
})
