import { describe, expect, it } from 'vitest'
import type { CtxGaps, CtxInsights } from '../../api/types'
import { suggestChecks, templateCsv } from './checkSuggestions'

const insights: CtxInsights = {
  ontology: { id: 'salt', name: 'salt' },
  kpis: [
    { label: 'Order Line', value: 2319540, question: 'How many Order Line records?' },
    { label: 'Customer', value: 139611, question: 'How many Customer records?' },
  ],
  charts: [
    { id: 'a', kind: 'bar', title: 'Order Lines by Incoterms', x: ['DDP', 'FCA'], y: [1466849, 500000],
      y_label: 'records', question: 'What is the Order Line count by Incoterms?' },
    { id: 'b', kind: 'line', title: 'Sales Documents per month', x: ['2020-02', '2020-03'], y: [1, 2],
      y_label: 'records', question: 'How many Sales Documents per month?' },
    { id: 'c', kind: 'bar', title: 'Empty', x: [], y: [], y_label: '', question: 'Nothing?' },
  ],
  questions: [],
}

const gaps: CtxGaps = {
  ontology: 'salt', total: 2, reasons: {},
  groups: [
    { key: 'a', question: 'What is the carbon footprint of each plant?', count: 2, reason: 'not_enough', label: '',
      detail: '', things: [], sources: ['context'], first: '', last: '', fix: { action: 'note', text: '', note: '' } },
    { key: 'b', question: 'Why did sales drop?', count: 1, reason: 'unverified', label: '',
      detail: '', things: [], sources: ['context'], first: '', last: '', fix: { action: 'metric', text: '', note: '' } },
  ],
}

describe('report check suggestions come from the data, never the number', () => {
  it('turns totals, breakdowns and months into checks, with the row to read', () => {
    const s = suggestChecks(insights, undefined, [])
    expect(s.map((x) => [x.question, x.row])).toEqual([
      ['How many Order Line records?', undefined],
      ['How many Customer records?', undefined],
      ['What is the Order Line count by Incoterms?', 'DDP'],          // the biggest row
      ['How many Sales Documents per month?', '2020-03'],            // the latest month
    ])
    expect(s.every((x) => !('expected' in x))).toBe(true)
  })

  it('turns questions Strata could not answer into should-refuse checks', () => {
    const s = suggestChecks(undefined, gaps, [])
    expect(s).toHaveLength(1)
    expect(s[0]).toMatchObject({ question: 'What is the carbon footprint of each plant?', refuse: true })
  })

  it('leaves out checks already added, whatever the case', () => {
    const s = suggestChecks(insights, gaps, ['how many customer records?'])
    expect(s.some((x) => x.question === 'How many Customer records?')).toBe(false)
    expect(s.length).toBe(4)
  })

  it('makes a CSV to fill in, numbers left blank', () => {
    const csv = templateCsv(suggestChecks(insights, gaps, []))
    const lines = csv.trim().split('\n')
    expect(lines[0]).toBe('question,expected,row,unit,digits,should refuse,other phrasings,source')
    expect(lines[3]).toBe('What is the Order Line count by Incoterms?,,DDP,,,,,')
    expect(lines[5]).toBe('What is the carbon footprint of each plant?,,,,,yes,,')
    expect(templateCsv([{ question: 'A, "b"', why: '' }]).split('\n')[1]).toBe('"A, ""b""",,,,,,,')
  })
})
