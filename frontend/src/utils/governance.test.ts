import { describe, expect, it } from 'vitest'
import { LAYER_FLOW, parseList, validationTone, verdictTone } from './governance'

describe('parseList', () => {
  it('splits on commas and new lines, trims and drops blanks', () => {
    expect(parseList('territory, area ,,\n zone ')).toEqual(['territory', 'area', 'zone'])
    expect(parseList('')).toEqual([])
  })

  it('drops case-insensitive duplicates, keeping the first spelling', () => {
    expect(parseList('Area, area, AREA')).toEqual(['Area'])
  })
})

describe('validationTone', () => {
  it('maps pass / warn / fail to badge tones', () => {
    expect(validationTone('pass')).toBe('teal')
    expect(validationTone('warn')).toBe('amber')
    expect(validationTone('fail')).toBe('rose')
    expect(validationTone('unknown')).toBe('neutral')
  })
})

describe('verdictTone', () => {
  it('maps the answerable verdict to badge tones', () => {
    expect(verdictTone('yes')).toBe('teal')
    expect(verdictTone('partial')).toBe('amber')
    expect(verdictTone('no')).toBe('rose')
    expect(verdictTone(undefined)).toBe('neutral')
  })
})

describe('LAYER_FLOW', () => {
  it('walks from the source through the four layers to agents', () => {
    expect(LAYER_FLOW.map((step) => step.to)).toEqual([
      '/onboarding', '/layers/ontology', '/layers/graph', '/layers/semantic',
      '/layers/context', '/agents',
    ])
    expect(LAYER_FLOW.map((step) => step.label)).toEqual([
      'Source', '1 Ontology', '2 Knowledge graph', '3 Semantic', '4 Context', 'Agents',
    ])
  })
})
