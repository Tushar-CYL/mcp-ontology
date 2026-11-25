import { useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from 'react'
import { Quote, Table2 } from 'lucide-react'
import type { KgOverview, KgSchemaTable } from '../../api/types'
import { formatCount } from '../../utils/onto'
import { cx } from '../../utils/cx'

type Layer = 'terms' | 'tables'

interface Bubble {
  id: string
  label: string
  subtitle: string
  size: number
  kind: Layer
  links: number
  fields?: number
  records?: number
  tables?: string[]
  description?: string
}

interface Link {
  id: string
  source: string
  target: string
  label: string
  weight: number
}

const W = 1200
const H = 640
const PAD = 56
/** Clear air between bubble edges — keeps the map readable. */
const GAP = 56
const LINK_LEN = 210

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}
const unit = (s: string) => (hash(s) % 10007) / 10007

function radiusFor(b: Bubble, maxSize: number): number {
  // Compact hubs like the NVIDIA-style map — size varies a little, never huge.
  const t = Math.sqrt(Math.max(1, b.size) / Math.max(1, maxSize))
  return Math.round(34 + t * 22)
}

function layout(nodes: Bubble[], links: Link[]): Map<string, { x: number; y: number; r: number }> {
  const n = nodes.length
  if (!n) return new Map()
  const maxSize = Math.max(...nodes.map((b) => b.size), 1)
  // Start widely spaced on a ring so the force sim has room to breathe.
  const ring = Math.min(W, H) * (0.28 + Math.min(0.18, n * 0.012))
  const placed = nodes.map((b, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n
    const jitter = (unit(b.id) - 0.5) * 36
    return {
      id: b.id,
      r: radiusFor(b, maxSize),
      x: W / 2 + Math.cos(a) * ring + jitter,
      y: H / 2 + Math.sin(a) * ring * 0.88 + jitter * 0.6,
    }
  })
  const index = new Map(placed.map((p, i) => [p.id, i]))
  const degree = new Float32Array(n)
  const pairs = links
    .map((l) => [index.get(l.source), index.get(l.target)] as const)
    .filter((p): p is readonly [number, number] => p[0] !== undefined && p[1] !== undefined)
  for (const [s, t] of pairs) {
    degree[s] += 1
    degree[t] += 1
  }
  const vx = new Float32Array(n)
  const vy = new Float32Array(n)
  const ticks = 280
  for (let tick = 0; tick < ticks; tick += 1) {
    const cool = 1 - tick / ticks
    const fx = new Float32Array(n)
    const fy = new Float32Array(n)
    // Strong pairwise repulsion — spread the cluster open.
    for (let i = 0; i < n; i += 1) {
      for (let j = i + 1; j < n; j += 1) {
        const a = placed[i]
        const b = placed[j]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dist = Math.hypot(dx, dy)
        if (dist < 0.5) {
          dx = unit(a.id + b.id) - 0.5
          dy = unit(b.id + a.id) - 0.5
          dist = 0.5
        }
        const min = a.r + b.r + GAP
        const soft = min * 2.8
        if (dist < soft) {
          const overlap = Math.max(0, min - dist)
          const push = (1200 / (dist * dist) + overlap * 0.55) * cool
          fx[i] += (dx / dist) * push
          fy[i] += (dy / dist) * push
          fx[j] -= (dx / dist) * push
          fy[j] -= (dy / dist) * push
        }
      }
    }
    // Gentle springs — linked nodes stay near, not stacked.
    for (const [s, tIdx] of pairs) {
      const dx = placed[tIdx].x - placed[s].x
      const dy = placed[tIdx].y - placed[s].y
      const dist = Math.max(1, Math.hypot(dx, dy))
      const ideal = LINK_LEN + (placed[s].r + placed[tIdx].r) * 0.35
      const pull = (dist - ideal) * 0.012
      fx[s] += (dx / dist) * pull
      fy[s] += (dy / dist) * pull
      fx[tIdx] -= (dx / dist) * pull
      fy[tIdx] -= (dy / dist) * pull
    }
    // Very light centering; unlinked nodes can float aside.
    for (let i = 0; i < n; i += 1) {
      const pullIn = degree[i] ? 0.0025 : 0.0008
      fx[i] += (W / 2 - placed[i].x) * pullIn
      fy[i] += (H / 2 - placed[i].y) * pullIn
      vx[i] = (vx[i] + fx[i]) * 0.78
      vy[i] = (vy[i] + fy[i]) * 0.78
      const r = placed[i].r
      placed[i].x = Math.max(PAD + r, Math.min(W - PAD - r, placed[i].x + vx[i]))
      placed[i].y = Math.max(PAD + r, Math.min(H - PAD - r, placed[i].y + vy[i]))
    }
  }
  // Final hard pass: no overlaps left.
  for (let pass = 0; pass < 40; pass += 1) {
    for (let i = 0; i < n; i += 1) {
      for (let j = i + 1; j < n; j += 1) {
        const a = placed[i]
        const b = placed[j]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dist = Math.hypot(dx, dy)
        const min = a.r + b.r + GAP
        if (dist < 0.01) {
          dx = 1
          dy = 0
          dist = 1
        }
        if (dist < min) {
          const push = (min - dist) / 2
          const ux = dx / dist
          const uy = dy / dist
          a.x += ux * push
          a.y += uy * push
          b.x -= ux * push
          b.y -= uy * push
        }
      }
    }
    for (const p of placed) {
      p.x = Math.max(PAD + p.r, Math.min(W - PAD - p.r, p.x))
      p.y = Math.max(PAD + p.r, Math.min(H - PAD - p.r, p.y))
    }
  }
  return new Map(placed.map((p) => [p.id, p]))
}

function short(label: string, max = 8): string {
  const clean = label.replace(/^olist[_ ]?/i, '').replace(/_/g, ' ')
  return clean.length <= max ? clean : `${clean.slice(0, max - 1)}…`
}

function buildTerms(o: KgOverview): { nodes: Bubble[]; links: Link[] } {
  const nodes: Bubble[] = o.things.map((t) => ({
    id: t.thing,
    label: t.thing,
    subtitle: 'Business term',
    size: Math.max(1, t.entities),
    kind: 'terms',
    links: o.connections.filter((c) => c.from_thing === t.thing || c.to_thing === t.thing).length,
    records: t.entities,
    tables: t.tables,
    description: t.tables.length
      ? `Drawn from ${t.tables.map((x) => x.split('.').pop()).join(', ')}.`
      : 'A kind of thing in this ontology.',
  }))
  const links: Link[] = o.connections.map((c) => ({
    id: c.key, source: c.from_thing, target: c.to_thing,
    label: c.label || `${c.from_thing} → ${c.to_thing}`, weight: c.connections,
  }))
  return { nodes, links }
}

function buildTables(o: KgOverview): { nodes: Bubble[]; links: Link[] } {
  const tables = o.schema.filter((t) => !t.graph)
  const nodes: Bubble[] = tables.map((t: KgSchemaTable) => ({
    id: t.table,
    label: t.table.split('.').pop() || t.table,
    subtitle: 'Source table',
    size: Math.max(1, t.rows ?? t.columns.length * 20),
    kind: 'tables',
    links: 0,
    fields: t.columns.length,
    records: t.rows ?? undefined,
    tables: [t.table],
    description: t.thing ? `Maps to the business term ${t.thing}.` : 'A table from your connected data.',
  }))
  const byThing = new Map<string, string[]>()
  for (const t of tables) {
    if (!t.thing) continue
    byThing.set(t.thing, [...(byThing.get(t.thing) ?? []), t.table])
  }
  const links: Link[] = []
  for (const c of o.connections) {
    for (const f of byThing.get(c.from_thing) ?? []) {
      for (const t of byThing.get(c.to_thing) ?? []) {
        if (f === t) continue
        links.push({ id: `${c.key}:${f}->${t}`, source: f, target: t, label: c.label, weight: c.connections })
      }
    }
  }
  const degree = new Map<string, number>()
  for (const l of links) {
    degree.set(l.source, (degree.get(l.source) ?? 0) + 1)
    degree.set(l.target, (degree.get(l.target) ?? 0) + 1)
  }
  for (const n of nodes) n.links = degree.get(n.id) ?? 0
  return { nodes, links }
}

/** Circular connections map — sits inside the same GraphPicture canvas shell. */
export function ExploreCanvas({ overview }: { overview: KgOverview }) {
  const [layer, setLayer] = useState<Layer>('terms')
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })
  const [hover, setHover] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null)
  const svg = useRef<SVGSVGElement | null>(null)

  const graph = useMemo(
    () => (layer === 'terms' ? buildTerms(overview) : buildTables(overview)),
    [overview, layer],
  )
  const pos = useMemo(() => layout(graph.nodes, graph.links), [graph])

  useEffect(() => {
    setSelected(null)
    setView({ x: 0, y: 0, k: 1 })
  }, [layer, overview.ontology.id])

  const selectedBubble = graph.nodes.find((n) => n.id === selected) ?? null
  const lit = useMemo(() => {
    const active = hover ?? selected
    if (!active) return null
    const s = new Set([active])
    for (const e of graph.links) {
      if (e.source === active) s.add(e.target)
      if (e.target === active) s.add(e.source)
    }
    return s
  }, [graph.links, hover, selected])

  // EY palette: charcoal bubbles, yellow rim and links.
  const fill = layer === 'terms' ? '#2e2e38' : '#3a3428'
  const stroke = layer === 'terms' ? '#ffe600' : '#e8c56a'
  const edge = layer === 'terms' ? '#ffe600' : '#e8c56a'

  const zoom = (factor: number, px = W / 2, py = H / 2) => setView((v) => {
    const k = Math.min(3.2, Math.max(0.45, v.k * factor))
    const r = k / v.k
    return { k, x: px - (px - v.x) * r, y: py - (py - v.y) * r }
  })
  const onWheel = (e: WheelEvent<SVGSVGElement>) => {
    const b = svg.current?.getBoundingClientRect()
    if (!b) return
    zoom(e.deltaY < 0 ? 1.12 : 0.89, ((e.clientX - b.left) / b.width) * W, ((e.clientY - b.top) / b.height) * H)
  }
  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0 || (e.target as Element).closest('.xpl-node')) return
    drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current
    const b = svg.current?.getBoundingClientRect()
    if (!d || !b) return
    const scale = W / b.width
    setView((v) => ({ ...v, x: d.vx + (e.clientX - d.x) * scale, y: d.vy + (e.clientY - d.y) * scale }))
  }

  return (
    <div className="xpl-canvas">
      <div className="xpl-canvas__switch" role="tablist" aria-label="Terms or tables">
        <button type="button" role="tab" aria-selected={layer === 'terms'}
          className={cx(layer === 'terms' && 'is-on')} onClick={() => setLayer('terms')}>
          <Quote size={13} aria-hidden="true" /> Terms
        </button>
        <button type="button" role="tab" aria-selected={layer === 'tables'}
          className={cx(layer === 'tables' && 'is-on')} onClick={() => setLayer('tables')}>
          <Table2 size={13} aria-hidden="true" /> Tables
        </button>
      </div>

      <svg ref={svg} className="xpl__svg" viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`${graph.nodes.length} ${layer}, ${graph.links.length} links`}
        onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove}
        onPointerUp={() => { drag.current = null }} onPointerLeave={() => { drag.current = null }}
        onClick={(e) => { if (!(e.target as Element).closest('.xpl-node')) setSelected(null) }}>
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {graph.links.map((l) => {
            const a = pos.get(l.source)
            const b = pos.get(l.target)
            if (!a || !b) return null
            const active = !lit || lit.has(l.source) || lit.has(l.target)
            return (
              <line key={l.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                className={cx('xpl__edge', !active && 'is-dim')} stroke={edge} />
            )
          })}
          {graph.nodes.map((n) => {
            const p = pos.get(n.id)
            if (!p) return null
            const active = !lit || lit.has(n.id)
            const on = selected === n.id
            return (
              <g key={n.id} className={cx('xpl-node', !active && 'is-dim', on && 'is-on')}
                transform={`translate(${p.x} ${p.y})`}
                onPointerEnter={() => setHover(n.id)}
                onPointerLeave={() => setHover(null)}
                onClick={(e) => { e.stopPropagation(); setSelected(n.id) }}
                style={{ cursor: 'pointer' }}>
                <circle r={p.r + 3} fill="none" stroke={stroke} strokeOpacity={0.28} strokeWidth={6} />
                <circle r={p.r} fill={fill} fillOpacity={on ? 1 : 0.94}
                  stroke={on ? '#ffe600' : stroke} strokeWidth={on ? 2.8 : 1.6} />
                <text textAnchor="middle" dominantBaseline="middle" className="xpl__label xpl__label--lite">
                  {short(n.label, p.r > 42 ? 9 : 7)}
                </text>
              </g>
            )
          })}
        </g>
      </svg>

      {selectedBubble ? (
        <aside className="xpl__card" aria-label={selectedBubble.label}>
          <div className="xpl__card-head">
            {selectedBubble.kind === 'terms'
              ? <Quote size={16} aria-hidden="true" />
              : <Table2 size={16} aria-hidden="true" />}
            <div>
              <h3>{selectedBubble.label}</h3>
              <p>{selectedBubble.subtitle}</p>
            </div>
          </div>
          <p className="xpl__card-desc">{selectedBubble.description}</p>
          <dl className="xpl__stats">
            {selectedBubble.records != null ? (
              <div><dt>Records</dt><dd>{formatCount(selectedBubble.records)}</dd></div>
            ) : null}
            {selectedBubble.fields != null ? (
              <div><dt>Columns</dt><dd>{formatCount(selectedBubble.fields)}</dd></div>
            ) : null}
            <div><dt>Links</dt><dd>{formatCount(selectedBubble.links)}</dd></div>
            {selectedBubble.tables?.length ? (
              <div><dt>Tables</dt><dd>{selectedBubble.tables.length}</dd></div>
            ) : null}
          </dl>
        </aside>
      ) : null}

      <div className="xpl__legend" aria-label="Legend">
        <span><i style={{ background: stroke }} /> {layer === 'terms' ? 'Term' : 'Table'} · {graph.nodes.length}</span>
        <span className="kg-muted">{graph.links.length} links</span>
      </div>
    </div>
  )
}
