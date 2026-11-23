/**
 * The globe picture's layout: each kind of thing is a globe (a circle of its
 * records) on a calm grid, and a light force pulls linked records together
 * while keeping every record inside its own globe's pull. Steady: the same
 * records always land in the same place (no random numbers).
 */

export interface GlobeNode { id: string; thing: string }
export interface GlobeEdge { source: string; target: string }
export type GlobeMode = 'globes' | 'web'

export interface Placed { id: string; x: number; y: number; r: number; degree: number }
export interface Globe { thing: string; x: number; y: number; r: number; count: number }

export const WIDTH = 1100
export const HEIGHT = 640
const PAD = 40

function hash(value: string): number {
  let out = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    out ^= value.charCodeAt(i)
    out = Math.imul(out, 16777619)
  }
  return out >>> 0
}
const unit = (v: string) => (hash(v) % 10007) / 10007

export function globeLayout(nodes: GlobeNode[], edges: GlobeEdge[], order: string[], mode: GlobeMode):
  { placed: Map<string, Placed>; globes: Globe[] } {
  const known = new Set(nodes.map((n) => n.id))
  const degree = new Map<string, number>()
  for (const e of edges) {
    if (!known.has(e.source) || !known.has(e.target)) continue
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
  }
  const things = [...new Set(nodes.map((n) => n.thing))].sort((a, b) => {
    const ai = order.indexOf(a)
    const bi = order.indexOf(b)
    return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi) || a.localeCompare(b)
  })
  // Up to eight globes sit on a ring (they read as connected worlds, with no
  // globe left alone in a corner); more than that, a calm grid.
  const cols = Math.max(1, Math.ceil(Math.sqrt(things.length * (WIDTH / HEIGHT))))
  const rows = Math.max(1, Math.ceil(things.length / cols))
  const ring = things.length >= 3 && things.length <= 8
  const centre = new Map(things.map((t, i) => {
    if (things.length === 1) return [t, { x: WIDTH / 2, y: HEIGHT / 2 }]
    if (things.length === 2) return [t, { x: WIDTH * (i === 0 ? 0.3 : 0.7), y: HEIGHT / 2 }]
    if (ring) {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / things.length
      return [t, { x: WIDTH / 2 + Math.cos(a) * WIDTH * 0.32, y: HEIGHT / 2 + 16 + Math.sin(a) * HEIGHT * 0.27 }]
    }
    return [t, { x: (WIDTH * ((i % cols) + 0.5)) / cols, y: (HEIGHT * (Math.floor(i / cols) + 0.5)) / rows }]
  }))

  const placed: Placed[] = []
  const thingOf = new Map<string, string>()
  for (const t of things) {
    const c = centre.get(t)!
    const members = nodes.filter((n) => n.thing === t)
      .sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) || a.id.localeCompare(b.id))
    members.forEach((n, i) => {
      // A sunflower spiral: the best-connected records sit in the middle.
      const angle = i * 2.399963229728653
      const radius = 6 + 11 * Math.sqrt(i)
      const d = degree.get(n.id) ?? 0
      placed.push({ id: n.id, degree: d, r: 4.5 + Math.min(6, Math.sqrt(Math.max(1, d)) * 1.8),
        x: c.x + Math.cos(angle) * radius, y: c.y + Math.sin(angle) * radius })
      thingOf.set(n.id, t)
    })
  }

  if (mode === 'web' && placed.length <= 900) {
    const index = new Map(placed.map((p, i) => [p.id, i]))
    const links = edges.map((e) => [index.get(e.source), index.get(e.target)])
      .filter((l): l is [number, number] => l[0] !== undefined && l[1] !== undefined)
    const ticks = placed.length > 450 ? 90 : 150
    const vx = new Float32Array(placed.length)
    const vy = new Float32Array(placed.length)
    for (let tick = 0; tick < ticks; tick += 1) {
      const fx = new Float32Array(placed.length)
      const fy = new Float32Array(placed.length)
      for (let i = 0; i < placed.length; i += 1) {
        for (let j = i + 1; j < placed.length; j += 1) {
          const a = placed[i]
          const b = placed[j]
          let dx = a.x - b.x
          let dy = a.y - b.y
          let dist = Math.hypot(dx, dy)
          if (dist < 0.5) { dx = unit(a.id + b.id) - 0.5; dy = unit(b.id + a.id) - 0.5; dist = 0.5 }
          if (dist < 220) {
            const f = 900 / (dist * dist)
            fx[i] += (dx / dist) * f; fy[i] += (dy / dist) * f
            fx[j] -= (dx / dist) * f; fy[j] -= (dy / dist) * f
          }
        }
      }
      for (const [s, t] of links) {
        const dx = placed[t].x - placed[s].x
        const dy = placed[t].y - placed[s].y
        const dist = Math.max(1, Math.hypot(dx, dy))
        const f = (dist - 60) * 0.01
        fx[s] += (dx / dist) * f; fy[s] += (dy / dist) * f
        fx[t] -= (dx / dist) * f; fy[t] -= (dy / dist) * f
      }
      for (let i = 0; i < placed.length; i += 1) {
        const p = placed[i]
        const c = centre.get(thingOf.get(p.id)!)!
        fx[i] += (c.x - p.x) * 0.02
        fy[i] += (c.y - p.y) * 0.02
        vx[i] = (vx[i] + fx[i]) * 0.7
        vy[i] = (vy[i] + fy[i]) * 0.7
        p.x = Math.max(PAD, Math.min(WIDTH - PAD, p.x + vx[i]))
        p.y = Math.max(PAD, Math.min(HEIGHT - PAD, p.y + vy[i]))
      }
    }
  }

  const globes: Globe[] = things.map((t) => {
    const c = centre.get(t)!
    const members = placed.filter((p) => thingOf.get(p.id) === t)
    const r = Math.max(28, ...members.map((p) => Math.hypot(p.x - c.x, p.y - c.y) + p.r)) + 14
    return { thing: t, x: c.x, y: c.y, r, count: members.length }
  })
  return { placed: new Map(placed.map((p) => [p.id, p])), globes }
}

/** A gentle curve between two records (so parallel lines do not overlap). */
export function curve(a: { x: number; y: number }, b: { x: number; y: number }, salt: string): string {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.max(1, Math.hypot(dx, dy))
  const off = (unit(salt) - 0.5) * 30
  const cx = (a.x + b.x) / 2 - (dy / len) * off
  const cy = (a.y + b.y) / 2 + (dx / len) * off
  return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`
}
