import { describe, expect, it } from 'vitest'
import { formatConfidence, formatLatency, formatNumber, humanize } from './format'

describe('format helpers', () => {
  it('renders numbers and refuses nonsense as an em dash', () => {
    expect(formatNumber(1234567.891)).toBe('1,234,567.89')
    expect(formatNumber('not a number')).toBe('—')
  })

  it('normalises confidence from 0..1 or 0..100', () => {
    expect(formatConfidence(0.84)).toBe('84%')
    expect(formatConfidence(84)).toBe('84%')
    expect(formatConfidence(7000)).toBe('100%')
  })

  it('formats latency at a human scale', () => {
    expect(formatLatency(8)).toBe('8 ms')
    expect(formatLatency(1240)).toBe('1.24 s')
  })

  it('turns tool ids into sentence case', () => {
    expect(humanize('compare_periods')).toBe('Compare periods')
  })
})
