import { describe, expect, it } from 'vitest'
import type { OntoField, OntoLink, OntoThing } from '../api/types'
import {
  CHECK, centralThing, checkedShare, conflictCount, filterFields, filterThings, flowLayout, matchLabel, sourceLine, timeAgo,
} from './onto'

function field(over: Partial<OntoField> = {}): OntoField {
  return {
    key: 's.t.c', table: 's.t', column: 'c', label: 'Thing', meaning: 'A thing', role: 'text',
    role_label: 'Free text', unit: null, type: 'VARCHAR', by: 'ai', check: 'verified',
    proof: 'text values', confidence: 0.9, links_to: null, ...over,
  }
}

function thing(name: string, fields: OntoField[] = [field()]): OntoThing {
  return { key: name, name, description: `${name} rows`, by: 'ai', tables: [`s.${name}`],
    records: 10, fields }
}

function link(a: string, b: string, cardinality = 'many-to-one'): OntoLink {
  return { key: `${a}-${b}`, from_thing: a, to_thing: b, from: 'x', to: 'y', cardinality,
    label: '', match: 1, proof: [] }
}

describe('onto helpers', () => {
  it('reads checks the same way everywhere', () => {
    expect(CHECK.conflict.tone).toBe('rose')
    expect(CHECK.verified.label).toBe('Checked in data')
  })

  it('computes the share of fields confirmed by the data', () => {
    expect(checkedShare({ things: 1, fields: 8, links: 0,
      checks: { verified: 6, conflict: 1, unchecked: 1 }, by: {} })).toBe(75)
    expect(checkedShare({ things: 0, fields: 0, links: 0,
      checks: { verified: 0, conflict: 0, unchecked: 0 }, by: {} })).toBe(0)
  })

  it('filters fields by text and by conflicts', () => {
    const fields = [field({ label: 'Order date', column: 'odt' }),
      field({ label: 'Status', check: 'conflict' }), field({ label: 'Fee', unit: 'EUR' })]
    expect(filterFields(fields, 'date', false).map((f) => f.label)).toEqual(['Order date'])
    expect(filterFields(fields, 'eur', false).map((f) => f.label)).toEqual(['Fee'])
    expect(filterFields(fields, '', true).map((f) => f.label)).toEqual(['Status'])
    expect(conflictCount(thing('T', fields))).toBe(1)
  })

  it('finds things by a field label too', () => {
    const things = [thing('Patient', [field({ label: 'Birth date' })]), thing('Doctor')]
    expect(filterThings(things, 'birth').map((t) => t.name)).toEqual(['Patient'])
    expect(filterThings(things, '  ')).toHaveLength(2)
  })

  it('formats small labels', () => {
    expect(matchLabel(0.987)).toBe('99% match')
    expect(matchLabel(null)).toBe('')
    expect(sourceLine(['a', 'b'], ['m.bim'])).toBe('2 data sources + 1 metadata file')
    expect(sourceLine([], [])).toBe('nothing connected')
  })

  it('opens on the most linked thing', () => {
    const things = [thing('Alpha'), thing('Order'), thing('Customer')]
    expect(centralThing({ things, links: [link('Order', 'Customer'), link('Alpha', 'Order')] }))
      .toBe('Order')
    expect(centralThing({ things: [], links: [] })).toBeUndefined()
  })

  it('lays the map out left to right, unlinked things underneath', () => {
    const things = ['Order Item', 'Order', 'Customer', 'Zip Code'].map((n) => thing(n))
    const links = [link('Order Item', 'Order'), link('Order', 'Customer', 'one-to-one'),
      link('Order', 'Order'), link('Order', 'Ghost')]
    const { nodes, edges } = flowLayout(things, links)
    const at = Object.fromEntries(nodes.map((n) => [n.id, n]))
    expect(edges.map((e) => e.label)).toEqual(['belongs to', 'has one'])
    expect(at['Order Item'].x).toBeLessThan(at.Order.x)
    expect(at.Order.x).toBeLessThan(at.Customer.x)
    expect(at['Zip Code'].y).toBeGreaterThan(Math.max(at.Order.y, at.Customer.y))
    expect(nodes).toHaveLength(4)
  })

  it('draws one map line per pair of things', () => {
    const things = ['Method', 'Task'].map((n) => thing(n))
    const verb = (v: string): OntoLink => ({ ...link('Method', 'Task'), key: v, verb: v })
    const { edges } = flowLayout(things, [verb('uses'), verb('solves'), verb('uses')])
    expect(edges).toEqual([{ id: 'Method->Task', source: 'Method', target: 'Task', label: '2 relations', directed: true }])
    expect(flowLayout(things, [verb('solves')]).edges[0].label).toBe('solves')
  })

  it('puts a dense graph on a circle, one line per pair both ways', () => {
    const names = ['Method', 'Task', 'Metric', 'Material', 'Other']
    const things = names.map((n) => thing(n))
    const links: OntoLink[] = []
    for (const a of names) for (const b of names) if (a !== b) links.push({ ...link(a, b), key: `${a}${b}`, verb: 'uses' })
    const out = flowLayout(things, links)
    expect(out.dense).toBe(true)
    expect(out.edges).toHaveLength(10)                    // 5 things: 10 pairs, not 20 arrows
    expect(out.edges.every((e) => !e.directed && e.label === '2 relations')).toBe(true)
    expect(new Set(out.nodes.map((n) => `${n.x},${n.y}`)).size).toBe(5)
  })

  it('says how long ago', () => {
    const now = Date.parse('2026-11-05T12:00:00Z')
    expect(timeAgo('2026-11-05T11:59:30Z', now)).toBe('just now')
    expect(timeAgo('2026-11-05T11:57:00Z', now)).toBe('3 minutes ago')
    expect(timeAgo('2026-11-05T10:00:00Z', now)).toBe('2 hours ago')
    expect(timeAgo('2026-11-03T12:00:00Z', now)).toBe('2 days ago')
    expect(timeAgo(null)).toBe('')
  })
})
