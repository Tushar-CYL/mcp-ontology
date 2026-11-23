import { describe, expect, it } from 'vitest'
import { proofWord, type Proof } from './proof'

describe('proof marks', () => {
  it('has a plain word for every kind', () => {
    const kinds: Proof[] = ['proved', 'guess', 'rule', 'disagrees', 'person', 'company']
    for (const k of kinds) {
      expect(proofWord(k)).toBeTruthy()
      expect(proofWord(k).length).toBeLessThan(20)
    }
  })

  it('names company meaning and data disagreement in business words', () => {
    expect(proofWord('company')).toMatch(/meaning/i)
    expect(proofWord('disagrees')).toMatch(/disagree/i)
  })
})
