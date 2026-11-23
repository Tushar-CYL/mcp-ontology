import { useMemo, useRef, useState, type PointerEvent, type WheelEvent } from 'react'
import { HEIGHT, WIDTH, curve, globeLayout, type GlobeMode } from './globeLayout'

interface Props {
  nodes: Array<{ id: string; thing: string; label: string | null; key: string }>
  edges: Array<{ id: string; source: string; target: string; label: string }>
  colours: Map<string, string>
  order: string[]
  totals: Map<string, number>
  mode: GlobeMode
  selected: string | null
  onSelect: (id: string) => void
}

const short = (s: string) => (s.length > 26 ? `${s.slice(0, 25)}…` : s)

/** The knowledge graph at a glance: one globe per kind of thing, its real
 *  records inside, real links between them. Hover lights up a record's
 *  links; click opens it. Wheel to zoom, drag to move. */
export function GlobeGraph({ nodes, edges, colours, order, totals, mode, selected, onSelect }: Props) {
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })
  const [hover, setHover] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null)
  const svg = useRef<SVGSVGElement | null>(null)

  const { placed, globes } = useMemo(() => globeLayout(nodes, edges, order, mode), [nodes, edges, order, mode])

  const lit = useMemo(() => {
    const active = hover ?? selected
    if (!active) return null
    const s = new Set([active])
    for (const e of edges) {
      if (e.source === active) s.add(e.target)
      if (e.target === active) s.add(e.source)
    }
    return s
  }, [edges, hover, selected])

  // One name per globe (its busiest record) keeps the picture readable.
  const named = useMemo(() => {
    const best = new Map<string, { id: string; d: number }>()
    for (const n of nodes) {
      const d = placed.get(n.id)?.degree ?? 0
      const cur = best.get(n.thing)
      if (!cur || d > cur.d) best.set(n.thing, { id: n.id, d })
    }
    return new Set([...best.values()].map((b) => b.id))
  }, [nodes, placed])

  const zoom = (factor: number, px = WIDTH / 2, py = HEIGHT / 2) => setView((v) => {
    const k = Math.min(4, Math.max(0.5, v.k * factor))
    const r = k / v.k
    return { k, x: px - (px - v.x) * r, y: py - (py - v.y) * r }
  })
  const onWheel = (e: WheelEvent<SVGSVGElement>) => {
    const b = svg.current?.getBoundingClientRect()
    if (!b) return
    zoom(e.deltaY < 0 ? 1.12 : 0.89, ((e.clientX - b.left) / b.width) * WIDTH, ((e.clientY - b.top) / b.height) * HEIGHT)
  }
  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0 || (e.target as Element).closest('.globe-node')) return
    drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current
    const b = svg.current?.getBoundingClientRect()
    if (!d || !b) return
    const scale = WIDTH / b.width
    setView((v) => ({ ...v, x: d.vx + (e.clientX - d.x) * scale, y: d.vy + (e.clientY - d.y) * scale }))
  }

  return (
    <div className="globe">
      <svg ref={svg} className="globe__svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img"
        aria-label={`Knowledge graph: ${nodes.length} records in ${globes.length} groups, ${edges.length} links`}
        onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove}
        onPointerUp={() => { drag.current = null }} onPointerLeave={() => { drag.current = null }}>
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {globes.map((g) => {
            const c = colours.get(g.thing) ?? '#747480'
            const total = totals.get(g.thing)
            const ty = g.y - g.r - 8 >= 16 ? g.y - g.r - 8 : g.y + g.r + 16
            return (
              <g key={g.thing} aria-hidden="true">
                <circle className="globe__halo" cx={g.x} cy={g.y} r={g.r} style={{ fill: c, stroke: c }} />
                <text className="globe__name" x={g.x} y={ty} textAnchor="middle">
                  {g.thing}{total ? ` · ${total.toLocaleString()}` : ''}
                </text>
              </g>
            )
          })}
          {edges.map((e) => {
            const a = placed.get(e.source)
            const b = placed.get(e.target)
            if (!a || !b) return null
            const on = !lit || (lit.has(e.source) && lit.has(e.target))
            return (
              <path key={e.id} className={`globe__line${on && lit ? ' is-lit' : ''}`} d={curve(a, b, e.id)}
                style={{ opacity: on ? undefined : 0.05 }}>
                <title>{e.label}</title>
              </path>
            )
          })}
          {nodes.map((n) => {
            const p = placed.get(n.id)
            if (!p) return null
            const c = colours.get(n.thing) ?? '#747480'
            const on = !lit || lit.has(n.id)
            const isSel = selected === n.id
            const name = n.label ?? n.key
            const showName = isSel || hover === n.id || named.has(n.id) || nodes.length <= 40
            const right = p.x < WIDTH - 180
            return (
              <g key={n.id} className="globe-node" transform={`translate(${p.x} ${p.y})`} opacity={on ? 1 : 0.18}
                role="button" tabIndex={0} aria-label={`${n.thing}: ${name}`}
                onClick={() => onSelect(n.id)} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}
                onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect(n.id) } }}>
                <circle r={p.r + (isSel || hover === n.id ? 4 : 0)} className="globe__ring" />
                <circle r={p.r} style={{ fill: c }} className={`globe__dot${isSel ? ' is-selected' : ''}`} />
                {showName ? (
                  <text className="globe__label" x={right ? p.r + 6 : -(p.r + 6)} y={4} textAnchor={right ? 'start' : 'end'}>
                    {short(name)}
                  </text>
                ) : null}
                <title>{`${name}\n${n.thing} · ${p.degree} link${p.degree === 1 ? '' : 's'} shown\nClick to open`}</title>
              </g>
            )
          })}
        </g>
      </svg>
      <div className="globe__zoom" role="group" aria-label="Zoom">
        <button type="button" onClick={() => zoom(1.2)} aria-label="Zoom in">+</button>
        <button type="button" onClick={() => zoom(0.84)} aria-label="Zoom out">−</button>
        <button type="button" onClick={() => setView({ x: 0, y: 0, k: 1 })} aria-label="Reset view">1:1</button>
      </div>
    </div>
  )
}
