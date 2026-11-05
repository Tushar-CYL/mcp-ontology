import { useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { EoMapNode } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { useAsync } from '../../hooks/useAsync'
import { layoutMap } from '../../utils/eo'

/**
 * The knowledge map: which source tables sit behind each concept (the MDM
 * master highlighted), how concepts link (with measured cardinality), and
 * the drill paths found in the data.
 */
export function KnowledgeMap({ oid, version }: { oid: string; version: number }) {
  const result = useAsync((signal) => api.eoMap(oid, signal), [oid, version])
  const [picked, setPicked] = useState<EoMapNode | null>(null)
  const placed = useMemo(() => (result.data ? layoutMap(result.data) : null), [result.data])

  if (result.initialLoading) return <LoadingState label="Drawing the map" />
  if (result.error) return <ErrorState error={result.error} onRetry={result.reload} />
  if (!placed || !placed.nodes.length) {
    return <EmptyState title="Nothing to draw yet" description="Run the accelerator to propose concepts." />
  }
  return (
    <div className="panel-stack">
      <Card title="Knowledge map" subtitle="Source tables on the left, concepts in the middle, drill paths on the right." bodyPadding="none">
        <div className="eo-map">
          <svg viewBox={`0 0 ${placed.width} ${placed.height}`} width="100%" role="img"
            aria-label="Concepts, the source tables behind them and how they link">
            <defs>
              <marker id="eo-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0,0 L10,5 L0,10 z" className="eo-map__arrow" />
              </marker>
            </defs>
            {placed.edges.map((e, i) => (
              <g key={i} className={`eo-map__edge eo-map__edge--${e.type}`}>
                <path d={e.path} markerEnd={e.type === 'relationship' ? 'url(#eo-arrow)' : undefined}>
                  <title>{e.detail ?? e.label}</title>
                </path>
                {e.type === 'relationship' ? <text x={e.lx} y={e.ly} className="eo-map__edge-label">{e.label}</text> : null}
              </g>
            ))}
            {placed.nodes.map((n) => (
              <g key={n.id} className={`eo-map__node eo-map__node--${n.type}${n.master ? ' is-master' : ''}${picked?.id === n.id ? ' is-picked' : ''}`}
                transform={`translate(${n.x},${n.y})`} onClick={() => setPicked(n)} role="button" tabIndex={0}
                onKeyDown={(ev) => { if (ev.key === 'Enter') setPicked(n) }}>
                <rect width={n.w} height={n.h} rx={n.type === 'concept' ? 10 : 6} />
                <text x={12} y={n.type === 'concept' ? 22 : n.h / 2 + 4}>{n.label}</text>
                {n.type === 'concept' ? (
                  <text x={12} y={40} className="eo-map__sub">{n.tier ?? n.status ?? ''}{n.owner ? ` · ${n.owner}` : ''}</text>
                ) : null}
              </g>
            ))}
          </svg>
        </div>
      </Card>
      <Card title={picked ? picked.label : 'Pick a node'}>
        {picked ? (
          <div className="stack">
            <div className="chip-row">
              <Badge tone="indigo">{picked.type}</Badge>
              {picked.tier ? <Badge tone="slate">{picked.tier}</Badge> : null}
              {picked.master ? <Badge tone="amber">MDM master</Badge> : null}
              {picked.status ? <Badge tone={picked.status === 'approved' ? 'teal' : 'amber'}>{picked.status}</Badge> : null}
            </div>
            {picked.description ? <p>{picked.description}</p> : null}
            {picked.owner ? <p className="muted">Owner: {picked.owner}</p> : null}
            {picked.source ? <p className="muted">Source: {picked.source}</p> : null}
          </div>
        ) : <p className="muted">Click a concept, table or drill path for its details.</p>}
      </Card>
    </div>
  )
}
