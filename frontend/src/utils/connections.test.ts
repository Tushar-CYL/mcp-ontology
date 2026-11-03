import { describe, expect, it } from 'vitest'
import { agentSource, fillKey, formatLatency, keyStatus, toolLabel } from './connections'

describe('fillKey', () => {
  const snippet = '{"headers": {"Authorization": "Bearer <YOUR_KEY>"}}'

  it('substitutes a freshly issued key everywhere', () => {
    const filled = fillKey(`${snippet} ${snippet}`, 'strata_abc')
    expect(filled).not.toContain('<YOUR_KEY>')
    expect(filled.match(/strata_abc/g)).toHaveLength(2)
  })

  it('keeps the placeholder when no key is in hand', () => {
    expect(fillKey(snippet, null)).toBe(snippet)
    expect(fillKey(snippet, '')).toBe(snippet)
  })
})

describe('keyStatus', () => {
  it('reports revoked, unused and used keys', () => {
    expect(keyStatus({ revoked: true, last_used_at: null })).toEqual({
      label: 'Revoked', tone: 'rose',
    })
    expect(keyStatus({ revoked: false, last_used_at: null })).toEqual({
      label: 'Never used', tone: 'neutral',
    })
    expect(keyStatus({ revoked: false, last_used_at: '2026-11-03T10:00:00' })).toEqual({
      label: 'Active', tone: 'teal',
    })
  })
})

describe('agentSource', () => {
  it('reads every shape the API has used for an agent source', () => {
    expect(agentSource({ id: 'a', name: 'A', source_id: 'revenue' })).toBe('revenue')
    expect(agentSource({ id: 'a', name: 'A', sources: ['hr'] })).toBe('hr')
    expect(agentSource({ id: 'a', name: 'A', source: 'crm' })).toBe('crm')
    expect(agentSource({ id: 'a', name: 'A' })).toBe('')
  })
})

describe('toolLabel', () => {
  it('turns snake_case tool names into words', () => {
    expect(toolLabel('get_context')).toBe('Get context')
    expect(toolLabel('check_readiness')).toBe('Check readiness')
  })
})

describe('formatLatency', () => {
  it('uses milliseconds below a second and seconds above', () => {
    expect(formatLatency(null)).toBe('—')
    expect(formatLatency(4.6)).toBe('5 ms')
    expect(formatLatency(986)).toBe('986 ms')
    expect(formatLatency(414316)).toBe('414.3 s')
  })
})
