import { describe, expect, it } from 'vitest'
import { HEIGHT, WIDTH, globeLayout } from './globeLayout'

const nodes = [
  ...Array.from({ length: 12 }, (_, i) => ({ id: `c|${i}`, thing: 'Customer' })),
  ...Array.from({ length: 30 }, (_, i) => ({ id: `o|${i}`, thing: 'Order' })),
  { id: 'p|1', thing: 'Product' },
]
const edges = Array.from({ length: 30 }, (_, i) => ({ source: `o|${i}`, target: `c|${i % 12}` }))
  .concat([{ source: 'o|0', target: 'p|1' }, { source: 'o|0', target: 'missing|9' }])

describe('the globe picture', () => {
  it('draws one globe per kind of thing, holding all its records', () => {
    const { placed, globes } = globeLayout(nodes, edges, ['Order', 'Customer', 'Product'], 'globes')
    expect(globes.map((g) => [g.thing, g.count])).toEqual([['Order', 30], ['Customer', 12], ['Product', 1]])
    expect(placed.size).toBe(nodes.length)
    for (const g of globes) {
      for (const n of nodes.filter((x) => x.thing === g.thing)) {
        const p = placed.get(n.id)!
        expect(Math.hypot(p.x - g.x, p.y - g.y)).toBeLessThan(g.r)
      }
    }
  })

  it('counts only lines between records that are drawn, and puts the busiest in the middle', () => {
    const { placed, globes } = globeLayout(nodes, edges, [], 'globes')
    expect(placed.get('o|0')!.degree).toBe(2)          // the line to a missing record is not counted
    const customer = globes.find((g) => g.thing === 'Customer')!
    const busiest = placed.get('c|0')!                   // c|0..c|5 have 3 orders, the rest 2
    const quiet = placed.get('c|11')!
    expect(Math.hypot(busiest.x - customer.x, busiest.y - customer.y))
      .toBeLessThan(Math.hypot(quiet.x - customer.x, quiet.y - customer.y))
  })

  it('stays on the canvas and is the same every time, in both modes', () => {
    for (const mode of ['globes', 'web'] as const) {
      const a = globeLayout(nodes, edges, [], mode)
      const b = globeLayout(nodes, edges, [], mode)
      expect([...a.placed.values()]).toEqual([...b.placed.values()])
      for (const p of a.placed.values()) {
        expect(p.x).toBeGreaterThanOrEqual(0); expect(p.x).toBeLessThanOrEqual(WIDTH)
        expect(p.y).toBeGreaterThanOrEqual(0); expect(p.y).toBeLessThanOrEqual(HEIGHT)
      }
    }
  })
})
