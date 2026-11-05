import { describe, expect, it } from 'vitest'
import type { EoMap } from '../api/types'
import { findingInfo, groupBy, isMoneyProperty, layoutMap, neverAnalysed, methodLabel, pct, sortFindings, STEP_STATUS } from './eo'

const MAP: EoMap = {
  nodes: [
    { id: 'concept:Customer', type: 'concept', label: 'Customer' },
    { id: 'concept:SalesOrder', type: 'concept', label: 'SalesOrder' },
    { id: 'table:bi_crm.accounts', type: 'table', label: 'bi_crm.accounts', source: 'bi_crm' },
    { id: 'table:bi_erp.customers', type: 'table', label: 'bi_erp.customers', source: 'bi_erp' },
    { id: 'table:bi_erp.sales_orders', type: 'table', label: 'bi_erp.sales_orders', source: 'bi_erp' },
    { id: 'hierarchy:Customer:region>country', type: 'hierarchy', label: 'region > country' },
  ],
  edges: [
    { from: 'table:bi_crm.accounts', to: 'concept:Customer', type: 'member', label: 'member' },
    { from: 'table:bi_erp.customers', to: 'concept:Customer', type: 'member', label: 'member' },
    { from: 'table:bi_erp.sales_orders', to: 'concept:SalesOrder', type: 'member', label: 'member' },
    { from: 'concept:SalesOrder', to: 'concept:Customer', type: 'relationship', label: 'many-to-one' },
    { from: 'concept:Customer', to: 'hierarchy:Customer:region>country', type: 'hierarchy', label: 'drill path' },
    { from: 'concept:Ghost', to: 'concept:Customer', type: 'relationship', label: 'x' },
  ],
}

describe('knowledge map layout', () => {
  const placed = layoutMap(MAP)
  const at = (id: string) => placed.nodes.find((n) => n.id === id)!

  it('puts tables, concepts and drill paths in three columns', () => {
    expect(at('table:bi_crm.accounts').x).toBeLessThan(at('concept:Customer').x)
    expect(at('concept:Customer').x).toBeLessThan(at('hierarchy:Customer:region>country').x)
  })

  it('never overlaps two nodes in one column', () => {
    for (const a of placed.nodes) {
      for (const b of placed.nodes) {
        if (a === b || a.x !== b.x) continue
        const apart = a.y + a.h <= b.y || b.y + b.h <= a.y
        expect(apart).toBe(true)
      }
    }
  })

  it('places a concept level with its own tables', () => {
    const order = at('concept:SalesOrder')
    const table = at('table:bi_erp.sales_orders')
    expect(Math.abs((order.y + order.h / 2) - (table.y + table.h / 2))).toBeLessThan(60)
  })

  it('drops edges that point at nothing and draws the rest', () => {
    expect(placed.edges).toHaveLength(5)
    for (const e of placed.edges) expect(e.path.startsWith('M ')).toBe(true)
  })

  it('is sized to hold every node', () => {
    for (const n of placed.nodes) {
      expect(n.x + n.w).toBeLessThanOrEqual(placed.width)
      expect(n.y + n.h).toBeLessThanOrEqual(placed.height)
    }
  })

  it('copes with an empty map', () => {
    const empty = layoutMap({ nodes: [], edges: [] })
    expect(empty.nodes).toEqual([])
    expect(empty.height).toBeGreaterThan(0)
  })
})

describe('labels', () => {
  it('names every step status', () => {
    expect(Object.keys(STEP_STATUS).sort()).toEqual(['done', 'ready', 'review', 'waiting'])
  })

  it('explains findings and falls back for unknown types', () => {
    expect(findingInfo('wrong_amount_column').tone).toBe('rose')
    expect(findingInfo('some_new_thing').title).toBe('some new thing')
  })

  it('sorts the most serious findings first', () => {
    const sorted = sortFindings([{ type: 'stale_source' }, { type: 'zzz' },
      { type: 'wrong_amount_column' }])
    expect(sorted.map((f) => f.type)).toEqual(['wrong_amount_column', 'stale_source', 'zzz'])
  })

  it('describes how a mapping was decided', () => {
    expect(methodLabel('reconciliation')).toMatch(/another system/)
    expect(methodLabel(undefined)).toBe('unknown')
  })

  it('formats shares and groups items', () => {
    expect(pct(0.1234, 1)).toBe('12.3%')
    expect(pct(null)).toBe('-')
    expect(groupBy(['a1', 'b1', 'a2'], (s) => s[0])).toEqual([['a', ['a1', 'a2']], ['b', ['b1']]])
  })
})

describe('money properties', () => {
  it('include converted and unclassified amounts, not look-alikes', () => {
    for (const p of ['net_amount', 'net_amount_usd', 'net_amount_local', 'amount_unclassified'])
      expect(isMoneyProperty(p)).toBe(true)
    for (const p of ['quantity', 'record_count', 'amountish', 'identifier'])
      expect(isMoneyProperty(p)).toBe(false)
  })
})

describe('never analysed', () => {
  const step = (id: string, items: number) => ({ id, items })
  it('is true when only the intake exists', () => {
    expect(neverAnalysed([step('intake', 0), step('profile', 0), step('concepts', 0), step('publish', 0)])).toBe(true)
  })
  it('is false once any analysis step produced items', () => {
    expect(neverAnalysed([step('intake', 0), step('profile', 3), step('concepts', 0)])).toBe(false)
  })
  it('ignores governance steps and an empty list', () => {
    expect(neverAnalysed([step('intake', 0), step('drift', 4)])).toBe(false)
    expect(neverAnalysed([])).toBe(false)
  })
})
