import { describe, expect, it } from 'vitest'
import { LAYER_RESEARCH, layerResearch } from './research'

describe('layer research content', () => {
  it('covers the four layers in order', () => {
    expect(LAYER_RESEARCH.map((l) => l.id)).toEqual(['ontology', 'graph', 'semantic', 'context'])
    expect(LAYER_RESEARCH.map((l) => l.number)).toEqual([1, 2, 3, 4])
  })

  it('gives every layer a distinct plain analogy and question', () => {
    const analogies = new Set(LAYER_RESEARCH.map((l) => l.analogy))
    expect(analogies.size).toBe(4)
    for (const layer of LAYER_RESEARCH) {
      expect(layer.plain.length).toBeGreaterThan(40)
      expect(layer.question.endsWith('?')).toBe(true)
      expect(layer.strata.length).toBeGreaterThan(40)
    }
  })

  it('names companies, repos and evidence with real links', () => {
    for (const layer of LAYER_RESEARCH) {
      expect(layer.companies.length).toBeGreaterThanOrEqual(3)
      expect(layer.repos.length).toBeGreaterThanOrEqual(2)
      expect(layer.evidence.length).toBeGreaterThanOrEqual(1)
      for (const item of [...layer.companies, ...layer.repos, ...layer.evidence]) {
        expect(item.url).toMatch(/^https:\/\//)
      }
      for (const repo of layer.repos) {
        expect(repo.licence.length).toBeGreaterThan(0)
      }
    }
  })

  it('flags vendor-run evidence', () => {
    const all = LAYER_RESEARCH.flatMap((l) => l.evidence)
    expect(all.some((e) => e.bias !== undefined)).toBe(true)
  })

  it('looks a layer up by id', () => {
    expect(layerResearch('semantic').title).toBe('Semantic layer')
    expect(() => layerResearch('nope' as never)).toThrow()
  })
})
