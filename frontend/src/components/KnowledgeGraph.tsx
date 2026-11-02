import { useMemo, useRef, useState, type PointerEvent, type WheelEvent } from 'react'
import type { GraphEdge, GraphNode } from '../api/types'
import { colorFor } from '../config/palette'
import { formatNumber, humanize } from '../utils/format'

export type GraphLayout = 'force' | 'cluster'

interface KnowledgeGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  classOrder: string[]
  layout: GraphLayout
  showLabels: boolean
  height?: number
  onSelect: (node: GraphNode) => void
}

interface PositionedNode extends GraphNode {
  x: number
  y: number
  radius: number
  color: string
}

interface PositionedEdge {
  edge: GraphEdge
  path: string
  measured: boolean
}

interface ClusterHull {
  name: string
  x: number
  y: number
  radius: number
  color: string
  count: number
}

interface LayoutResult {
  nodes: PositionedNode[]
  edges: PositionedEdge[]
  clusters: ClusterHull[]
}

interface View {
  x: number
  y: number
  k: number
}

const WIDTH = 1040
const HEIGHT = 620
const PAD = 54

function hash(value: string): number {
  let out = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    out ^= value.charCodeAt(index)
    out = Math.imul(out, 16777619)
  }
  return out >>> 0
}

function unit(value: string): number {
  return (hash(value) % 10007) / 10007
}

function isMeasured(provenance?: string): boolean {
  return /^(measured|declared|stated|observed|exact)$/i.test(provenance ?? '')
}

function displayLabel(node: GraphNode): string {
  const label = (node.label ?? '').trim()
  const key = (node.key ?? node.id).trim()
  const looksLikeId = /^[A-Za-z]{1,3}\d{5,}$/.test(label) || /^\d{5,}$/.test(label)
  if (label && label !== key && !looksLikeId) return label
  const short = key.length > 18 ? `${key.slice(0, 8)}…${key.slice(-4)}` : key
  return `${humanize(node.class)} ${short}`
}

function buildPositions(
  nodes: GraphNode[],
  edges: GraphEdge[],
  classOrder: string[],
  layout: GraphLayout,
): LayoutResult {
  const classes = [...new Set(nodes.map((node) => node.class))]
  classes.sort((a, b) => {
    const ai = classOrder.indexOf(a)
    const bi = classOrder.indexOf(b)
    return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi) || a.localeCompare(b)
  })

  // Classes occupy a stable grid of clusters. A grid is calmer and more
  // legible than a ring when one class is much larger than the others.
  const columns = Math.max(1, Math.ceil(Math.sqrt(classes.length)))
  const rows = Math.max(1, Math.ceil(classes.length / columns))
  const centerOf = new Map<string, { x: number; y: number }>()
  classes.forEach((name, index) => {
    const column = index % columns
    const row = Math.floor(index / columns)
    centerOf.set(name, {
      x: (WIDTH * (column + 0.5)) / columns,
      y: (HEIGHT * (row + 0.5)) / rows,
    })
  })

  const groups = new Map<string, GraphNode[]>()
  for (const node of nodes) {
    const list = groups.get(node.class) ?? []
    list.push(node)
    groups.set(node.class, list)
  }

  const positioned: PositionedNode[] = []
  const byId = new Map<string, PositionedNode>()
  const colorIndex = new Map(classOrder.map((name, index) => [name, index]))

  for (const className of classes) {
    const group = (groups.get(className) ?? []).slice().sort(
      (a, b) => b.degree - a.degree || a.id.localeCompare(b.id),
    )
    const center = centerOf.get(className) ?? { x: WIDTH / 2, y: HEIGHT / 2 }
    const columns = Math.max(1, Math.ceil(Math.sqrt(group.length)))
    const spacing = layout === 'force' ? 26 : 34
    group.forEach((node, index) => {
      const row = Math.floor(index / columns)
      const column = index % columns
      const gridX = (column - (columns - 1) / 2) * spacing
      const gridY = (row - (Math.ceil(group.length / columns) - 1) / 2) * spacing
      const spiralAngle = index * 2.399963229728653
      const spiralRadius = 8 + 12.5 * Math.sqrt(index)
      const jitter = 5
      const color = colorFor(colorIndex.get(className) ?? 0)
      const radius = 6 + Math.min(7, Math.sqrt(Math.max(1, node.degree)) * 2.1)
      const item: PositionedNode = {
        ...node,
        color,
        radius,
        x: layout === 'cluster'
          ? center.x + Math.cos(spiralAngle) * spiralRadius
          : center.x + gridX + (unit(`${node.id}-x`) - 0.5) * jitter,
        y: layout === 'cluster'
          ? center.y + Math.sin(spiralAngle) * spiralRadius
          : center.y + gridY + (unit(`${node.id}-y`) - 0.5) * jitter,
      }
      positioned.push(item)
      byId.set(node.id, item)
    })
  }

  if (layout === 'force') {
    const indexById = new Map(positioned.map((node, index) => [node.id, index]))
    const links = edges
      .map((edge) => ({ edge, source: indexById.get(edge.source), target: indexById.get(edge.target) }))
      .filter((edge): edge is { edge: GraphEdge; source: number; target: number } =>
        edge.source !== undefined && edge.target !== undefined,
      )
    const iterations = nodes.length > 450 ? 110 : nodes.length > 250 ? 150 : 190
    const vx = new Float32Array(positioned.length)
    const vy = new Float32Array(positioned.length)

    for (let tick = 0; tick < iterations; tick += 1) {
      const fx = new Float32Array(positioned.length)
      const fy = new Float32Array(positioned.length)

      for (let i = 0; i < positioned.length; i += 1) {
        for (let j = i + 1; j < positioned.length; j += 1) {
          const a = positioned[i]
          const b = positioned[j]
          let dx = a.x - b.x
          let dy = a.y - b.y
          let distance = Math.hypot(dx, dy)
          if (distance < 0.5) {
            dx = (unit(`${a.id}${b.id}x`) - 0.5) * 2
            dy = (unit(`${a.id}${b.id}y`) - 0.5) * 2
            distance = 0.5
          }
          if (distance < 340) {
            const force = 3800 / (distance * distance)
            fx[i] += (dx / distance) * force
            fy[i] += (dy / distance) * force
            fx[j] -= (dx / distance) * force
            fy[j] -= (dy / distance) * force
          }
          const minDistance = a.radius + b.radius + 7
          if (distance < minDistance) {
            const push = (minDistance - distance) * 0.22
            fx[i] += (dx / distance) * push
            fy[i] += (dy / distance) * push
            fx[j] -= (dx / distance) * push
            fy[j] -= (dy / distance) * push
          }
        }
      }

      for (const link of links) {
        const a = positioned[link.source]
        const b = positioned[link.target]
        const dx = b.x - a.x
        const dy = b.y - a.y
        const distance = Math.max(1, Math.hypot(dx, dy))
        const force = (distance - 78) * 0.012
        fx[link.source] += (dx / distance) * force
        fy[link.source] += (dy / distance) * force
        fx[link.target] -= (dx / distance) * force
        fy[link.target] -= (dy / distance) * force
      }

      for (let index = 0; index < positioned.length; index += 1) {
        const node = positioned[index]
        const center = centerOf.get(node.class) ?? { x: WIDTH / 2, y: HEIGHT / 2 }
        fx[index] += (center.x - node.x) * 0.016
        fy[index] += (center.y - node.y) * 0.016
        fx[index] += (WIDTH / 2 - node.x) * 0.002
        fy[index] += (HEIGHT / 2 - node.y) * 0.002
        vx[index] = (vx[index] + fx[index]) * 0.72
        vy[index] = (vy[index] + fy[index]) * 0.72
        node.x = Math.max(PAD, Math.min(WIDTH - PAD, node.x + vx[index]))
        node.y = Math.max(PAD, Math.min(HEIGHT - PAD, node.y + vy[index]))
      }
    }
  }

  const clusters: ClusterHull[] = classes.map((name) => {
    const center = centerOf.get(name) ?? { x: WIDTH / 2, y: HEIGHT / 2 }
    const members = positioned.filter((node) => node.class === name)
    const radius = members.length === 0
      ? 34
      : Math.max(...members.map((node) => Math.hypot(node.x - center.x, node.y - center.y) + node.radius)) + 22
    return {
      name,
      x: center.x,
      y: center.y,
      radius,
      count: members.length,
      color: colorFor(colorIndex.get(name) ?? 0),
    }
  })

  const positionedById = new Map(positioned.map((node) => [node.id, node]))
  const curved: PositionedEdge[] = []
  for (const edge of edges) {
    const source = positionedById.get(edge.source)
    const target = positionedById.get(edge.target)
    if (!source || !target) continue
    const dx = target.x - source.x
    const dy = target.y - source.y
    const length = Math.max(1, Math.hypot(dx, dy))
    const offset = (unit(`${edge.relation}-${edge.source}-${edge.target}`) - 0.5) * 34
    const cx = (source.x + target.x) / 2 - (dy / length) * offset
    const cy = (source.y + target.y) / 2 + (dx / length) * offset
    curved.push({
      edge,
      path: `M ${source.x.toFixed(2)} ${source.y.toFixed(2)} Q ${cx.toFixed(2)} ${cy.toFixed(2)} ${target.x.toFixed(2)} ${target.y.toFixed(2)}`,
      measured: isMeasured(edge.provenance),
    })
  }
  return { nodes: positioned, edges: curved, clusters }
}

export function KnowledgeGraph({
  nodes,
  edges,
  classOrder,
  layout,
  showLabels,
  height = 560,
  onSelect,
}: KnowledgeGraphProps) {
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 })
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number; viewX: number; viewY: number } | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)

  const graph = useMemo(
    () => buildPositions(nodes, edges, classOrder, layout),
    [nodes, edges, classOrder, layout],
  )

  const classCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const node of nodes) counts.set(node.class, (counts.get(node.class) ?? 0) + 1)
    return counts
  }, [nodes])

  const classLegend = useMemo(
    () => [...classCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 7),
    [classCounts],
  )

  // One readable label per class is enough at overview scale; the legend and
  // click-through carry the rest. This avoids a wall of overlapping names.
  const priorityLabelIds = useMemo(() => {
    const best = new Map<string, GraphNode>()
    for (const node of nodes) {
      const current = best.get(node.class)
      if (!current || node.degree > current.degree) best.set(node.class, node)
    }
    return new Set([...best.values()].map((node) => node.id))
  }, [nodes])

  const connected = useMemo(() => {
    const active = hovered ?? selected
    if (!active) return null
    const set = new Set<string>([active])
    for (const edge of edges) {
      if (edge.source === active) set.add(edge.target)
      if (edge.target === active) set.add(edge.source)
    }
    return set
  }, [edges, hovered, selected])

  const choose = (node: GraphNode) => {
    setSelected(node.id)
    onSelect(node)
  }

  const zoomBy = (factor: number) => {
    setView((current) => {
      const next = Math.min(2.8, Math.max(0.65, current.k * factor))
      const ratio = next / current.k
      return {
        k: next,
        x: WIDTH / 2 - (WIDTH / 2 - current.x) * ratio,
        y: HEIGHT / 2 - (HEIGHT / 2 - current.y) * ratio,
      }
    })
  }

  const onWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault()
    const bounds = svgRef.current?.getBoundingClientRect()
    if (!bounds) return
    const px = ((event.clientX - bounds.left) / bounds.width) * WIDTH
    const py = ((event.clientY - bounds.top) / bounds.height) * HEIGHT
    const factor = event.deltaY < 0 ? 1.12 : 0.89
    setView((current) => {
      const next = Math.min(2.8, Math.max(0.65, current.k * factor))
      const ratio = next / current.k
      return {
        k: next,
        x: px - (px - current.x) * ratio,
        y: py - (py - current.y) * ratio,
      }
    })
  }

  const onPointerDown = (event: PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return
    drag.current = {
      x: event.clientX,
      y: event.clientY,
      viewX: view.x,
      viewY: view.y,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!drag.current) return
    setView((current) => ({
      ...current,
      x: drag.current ? drag.current.viewX + (event.clientX - drag.current.x) : current.x,
      y: drag.current ? drag.current.viewY + (event.clientY - drag.current.y) : current.y,
    }))
  }

  const onPointerUp = () => {
    drag.current = null
  }

  return (
    <div className="graph-stage" style={{ height }}>
      <svg
        ref={svgRef}
        className="graph-canvas"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Relationship graph with ${nodes.length} entities and ${edges.length} links`}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <defs>
          <pattern id="graph-grid" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" stroke="#e8edf4" strokeWidth="1" />
          </pattern>
          <linearGradient id="graph-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#f8fafc" stopOpacity="0.7" />
          </linearGradient>
        </defs>
        <rect width={WIDTH} height={HEIGHT} fill="#fbfcfe" />
        <rect width={WIDTH} height={HEIGHT} fill="url(#graph-grid)" opacity="0.75" />
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {layout === 'cluster'
            ? graph.clusters.map((cluster) => (
                <g key={`cluster-${cluster.name}`} className="graph-cluster" aria-hidden="true">
                  <circle
                    cx={cluster.x}
                    cy={cluster.y}
                    r={cluster.radius}
                    fill={cluster.color}
                    fillOpacity={0.04}
                    stroke={cluster.color}
                    strokeOpacity={0.18}
                    strokeDasharray="3 6"
                  />
                  <text
                    className="graph-cluster__label"
                    x={cluster.x}
                    y={
                      cluster.y - cluster.radius - 8 >= 20
                        ? cluster.y - cluster.radius - 8
                        : Math.min(HEIGHT - 14, cluster.y + cluster.radius + 14)
                    }
                    textAnchor="middle"
                    paintOrder="stroke"
                    stroke="#fbfcfe"
                    strokeWidth="4"
                  >
                    {cluster.name} · {formatNumber(cluster.count)}
                  </text>
                </g>
              ))
            : null}
          {graph.edges.map((item, index) => {
            const active = connected
              ? connected.has(item.edge.source) && connected.has(item.edge.target)
              : true
            return (
              <path
                key={`edge-${index}-${item.edge.relation}`}
                d={item.path}
                fill="none"
                stroke={item.measured ? '#64748b' : '#b6a27a'}
                strokeWidth={item.measured ? 1.1 : 0.95}
                strokeDasharray={item.measured ? undefined : '4 5'}
                strokeOpacity={active ? (layout === 'cluster' ? 0.17 : item.measured ? 0.48 : 0.38) : 0.05}
              >
                <title>{`${humanize(item.edge.relation)} · ${item.measured ? 'declared' : 'inferred'}`}</title>
              </path>
            )
          })}
          {graph.nodes.map((node) => {
            const isActive = connected ? connected.has(node.id) : true
            const isSelected = selected === node.id
            const isHovered = hovered === node.id
            const show =
              showLabels &&
              (nodes.length <= 40 || priorityLabelIds.has(node.id) || isSelected || isHovered)
            const label = displayLabel(node)
            return (
              <g
                key={node.id}
                className="graph-node"
                opacity={isActive ? 1 : 0.2}
                transform={`translate(${node.x} ${node.y})`}
                onClick={(event) => {
                  event.stopPropagation()
                  choose(node)
                }}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    choose(node)
                  }
                }}
                aria-label={`${node.class}: ${label}`}
              >
                <circle r={node.radius + (isSelected || isHovered ? 5 : 0)} fill="#ffffff" opacity={0.9} />
                <circle
                  r={node.radius}
                  fill={node.color}
                  stroke={isSelected ? '#0f172a' : '#ffffff'}
                  strokeWidth={isSelected ? 2.5 : 2}
                />
                {show ? (
                  <text
                    className="graph-node__label"
                    x={node.x < WIDTH - 190 ? node.radius + 7 : -(node.radius + 7)}
                    y={4}
                    textAnchor={node.x < WIDTH - 190 ? 'start' : 'end'}
                    paintOrder="stroke"
                    stroke="#ffffff"
                    strokeWidth="4"
                    strokeLinejoin="round"
                  >
                    {label.length > 28 ? `${label.slice(0, 27)}…` : label}
                  </text>
                ) : null}
                <title>{`${label}\n${node.class} · ${formatNumber(node.degree)} connections\nClick for details`}</title>
              </g>
            )
          })}
        </g>
      </svg>

      <div className="graph-legend" aria-label="Legend">
        {classLegend.map(([name, count]) => (
          <span className="graph-legend__item" key={name}>
            <span
              className="graph-legend__dot"
              style={{ background: colorFor(classOrder.indexOf(name)) }}
            />
            {name}
            <span className="graph-legend__count">{formatNumber(count)}</span>
          </span>
        ))}
        <span className="graph-legend__rule">
          <span className="graph-legend__line graph-legend__line--solid" /> declared
        </span>
        <span className="graph-legend__rule">
          <span className="graph-legend__line graph-legend__line--dashed" /> inferred
        </span>
      </div>

      <div className="graph-zoom" role="group" aria-label="Graph zoom">
        <button type="button" onClick={() => zoomBy(1.2)} aria-label="Zoom in">
          +
        </button>
        <button type="button" onClick={() => zoomBy(0.84)} aria-label="Zoom out">
          −
        </button>
        <button type="button" onClick={() => setView({ x: 0, y: 0, k: 1 })} aria-label="Reset view">
          1:1
        </button>
      </div>
    </div>
  )
}
