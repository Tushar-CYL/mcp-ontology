import { useMemo, useState } from 'react'
import type { OntologyClass, OntologyRelation } from '../api/types'
import { colorFor } from '../config/palette'
import { formatNumber } from '../utils/format'

interface OntologyDiagramProps {
  classes: OntologyClass[]
  relations: OntologyRelation[]
}

interface Box {
  item: OntologyClass
  x: number
  y: number
  width: number
  height: number
  color: string
}

const BOX_WIDTH = 212
const BOX_HEIGHT = 84
const GAP_X = 58
const GAP_Y = 82
const COLUMNS = 3
const WIDTH = COLUMNS * BOX_WIDTH + (COLUMNS + 1) * GAP_X
const MAX_CLASSES = 9
const MAX_RELATIONS = 14

function isDeclared(provenance?: string): boolean {
  return /^(measured|declared|stated|observed|exact)$/i.test(provenance ?? '')
}

export function OntologyDiagram({ classes, relations }: OntologyDiagramProps) {
  const [hovered, setHovered] = useState<string | null>(null)

  const shownClasses = useMemo(
    () => classes.slice(0, MAX_CLASSES),
    [classes],
  )
  const shownRelations = useMemo(() => {
    const names = new Set(shownClasses.map((item) => item.name))
    return relations
      .filter((relation) => names.has(relation.domain) && names.has(relation.range))
      .slice(0, MAX_RELATIONS)
  }, [relations, shownClasses])

  const rows = Math.ceil(shownClasses.length / COLUMNS)
  const height = rows * BOX_HEIGHT + (rows + 1) * GAP_Y + 70

  const boxes = useMemo<Box[]>(() => shownClasses.map((item, index) => {
    const column = index % COLUMNS
    const row = Math.floor(index / COLUMNS)
    return {
      item,
      x: GAP_X + column * (BOX_WIDTH + GAP_X),
      y: 48 + row * (BOX_HEIGHT + GAP_Y),
      width: BOX_WIDTH,
      height: BOX_HEIGHT,
      color: colorFor(index),
    }
  }), [shownClasses])

  const byName = useMemo(() => new Map(boxes.map((box) => [box.item.name, box])), [boxes])

  const edges = useMemo(() => {
    return shownRelations.flatMap((relation, index) => {
      const source = byName.get(relation.domain)
      const target = byName.get(relation.range)
      if (!source || !target) return []
      if (source.item.name === target.item.name) return []
      const leftToRight = source.x < target.x
      const sx = source.x + (leftToRight ? source.width : 0)
      const sy = source.y + source.height / 2
      const tx = target.x + (leftToRight ? 0 : target.width)
      const ty = target.y + target.height / 2
      const bend = (index % 2 === 0 ? 1 : -1) * 34
      const cx = (sx + tx) / 2
      const cy = (sy + ty) / 2 + bend
      return [{
        relation,
        path: `M ${sx} ${sy} C ${cx} ${sy}, ${cx} ${ty}, ${tx} ${ty}`,
        labelX: cx,
        labelY: cy - 7,
        declared: isDeclared(relation.provenance),
      }]
    })
  }, [byName, shownRelations])

  const activeRelations = useMemo(() => {
    if (!hovered) return null
    return new Set(
      shownRelations
        .filter((relation) => relation.domain === hovered || relation.range === hovered)
        .map((relation) => relation.name),
    )
  }, [hovered, shownRelations])

  if (shownClasses.length === 0) {
    return <p className="muted">The source did not expose any classes to draw.</p>
  }

  return (
    <div className="ontology-map">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label={`Schema map with ${shownClasses.length} classes and ${shownRelations.length} relationships`}
      >
        <defs>
          <marker id="ontology-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
          <pattern id="ontology-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#edf1f6" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width={WIDTH} height={height} fill="#fcfdff" />
        <rect width={WIDTH} height={height} fill="url(#ontology-grid)" opacity="0.7" />

        <text className="ontology-map__eyebrow" x={GAP_X} y={26}>
          LOGICAL SCHEMA
        </text>

        {edges.map((edge, index) => {
          const active = !activeRelations || activeRelations.has(edge.relation.name)
          return (
            <g key={`${edge.relation.name}-${index}`} opacity={active ? 1 : 0.12}>
              <path
                d={edge.path}
                fill="none"
                stroke={edge.declared ? '#64748b' : '#b6a27a'}
                strokeWidth={edge.declared ? 1.3 : 1.1}
                strokeDasharray={edge.declared ? undefined : '4 5'}
                markerEnd="url(#ontology-arrow)"
              />
              <rect
                x={edge.labelX - Math.min(92, edge.relation.name.length * 3.4)}
                y={edge.labelY - 9}
                width={Math.min(184, edge.relation.name.length * 6.8)}
                height={16}
                rx={8}
                fill="#ffffff"
                stroke="#e2e8f0"
              />
              <text className="ontology-map__edge-label" x={edge.labelX} y={edge.labelY + 3} textAnchor="middle">
                {edge.relation.name.length > 26 ? `${edge.relation.name.slice(0, 25)}…` : edge.relation.name}
              </text>
            </g>
          )
        })}

        {boxes.map((box) => {
          const active = !hovered || hovered === box.item.name
          return (
            <g
              key={box.item.name}
              className="ontology-box"
              opacity={active ? 1 : 0.45}
              onMouseEnter={() => setHovered(box.item.name)}
              onMouseLeave={() => setHovered(null)}
            >
              <rect
                x={box.x}
                y={box.y}
                width={box.width}
                height={box.height}
                rx={10}
                fill="#ffffff"
                stroke="#dfe5ee"
              />
              <rect x={box.x} y={box.y} width={4} height={box.height} rx={2} fill={box.color} />
              <text className="ontology-box__title" x={box.x + 16} y={box.y + 24}>
                {box.item.name.length > 20 ? `${box.item.name.slice(0, 19)}…` : box.item.name}
              </text>
              <text className="ontology-box__meta" x={box.x + 16} y={box.y + 43}>
                {box.item.table || 'derived class'}
              </text>
              <text className="ontology-box__meta" x={box.x + 16} y={box.y + 61}>
                key: {box.item.key || '—'}
              </text>
              <text className="ontology-box__count" x={box.x + box.width - 16} y={box.y + 24} textAnchor="end">
                {formatNumber(box.item.count)}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="ontology-map__footer">
        <span>Declared links are solid; inferred links are dashed.</span>
        {classes.length > MAX_CLASSES ? <span>Showing the {MAX_CLASSES} largest classes of {classes.length}.</span> : null}
        {relations.length > shownRelations.length ? <span>{relations.length - shownRelations.length} further links in the tables below.</span> : null}
      </div>
    </div>
  )
}
