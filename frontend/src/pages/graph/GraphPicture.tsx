import { useCallback, useEffect, useMemo, useState } from 'react'
import { Background, Controls, Position, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import { Lock, Plus, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { KgPicture } from '../../api/types'
import { Button } from '../../components/Button'
import { LoadingState } from '../../components/LoadingState'
import { useAsync } from '../../hooks/useAsync'
import { EntityPicker } from './EntityPicker'

type GNode = KgPicture['nodes'][number]
type GEdge = KgPicture['edges'][number]

// One colour per kind of thing (EY palette first, then calm neutrals).
const PALETTE = ['#ffe600', '#2e2e38', '#188ce5', '#2db757', '#ff6d00', '#b9251c', '#9c82d4', '#27acaa', '#ff4136', '#747480']
const NODE_W = 170
const NODE_H = 34

const ROW_WIDTH = 1500    // groups are packed into rows about this wide (the canvas is wide)
const GAP = 60

/**
 * Each separate group of connected records is laid out on its own (left to
 * right), then the groups are packed side by side in rows. One tall column
 * of groups would force the view to zoom out until names cannot be read.
 */
function layout(nodes: GNode[], edges: GEdge[]): Map<string, { x: number; y: number }> {
  const parent = new Map(nodes.map((n) => [n.id, n.id]))
  const root = (id: string): string => {
    let r = id
    while (parent.get(r) !== r) r = parent.get(r)!
    parent.set(id, r)
    return r
  }
  edges.forEach((e) => {
    if (parent.has(e.source) && parent.has(e.target)) parent.set(root(e.source), root(e.target))
  })
  const groups = new Map<string, GNode[]>()
  nodes.forEach((n) => groups.set(root(n.id), [...(groups.get(root(n.id)) ?? []), n]))

  const out = new Map<string, { x: number; y: number }>()
  let x = 0
  let y = 0
  let rowHeight = 0
  for (const members of [...groups.values()].sort((a, b) => b.length - a.length)) {
    const ids = new Set(members.map((m) => m.id))
    const g = new dagre.graphlib.Graph()
    g.setGraph({ rankdir: 'LR', nodesep: 12, ranksep: 70 })
    g.setDefaultEdgeLabel(() => ({}))
    members.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }))
    edges.forEach((e) => { if (ids.has(e.source) && ids.has(e.target)) g.setEdge(e.source, e.target) })
    dagre.layout(g)
    const w = g.graph().width ?? NODE_W
    const h = g.graph().height ?? NODE_H
    if (x > 0 && x + w > ROW_WIDTH) { x = 0; y += rowHeight + GAP; rowHeight = 0 }
    members.forEach((n) => {
      const p = g.node(n.id)
      out.set(n.id, { x: x + p.x - NODE_W / 2, y: y + p.y - NODE_H / 2 })
    })
    x += w + GAP
    rowHeight = Math.max(rowHeight, h)
  }
  return out
}

/** The knowledge graph as a picture of real records. Click to see one; expand to grow. */
export function GraphPicture({ oid }: { oid: string }) {
  const first = useAsync((signal) => api.kgSample(oid, signal), [oid])
  const [nodes, setNodes] = useState<GNode[]>([])
  const [edges, setEdges] = useState<GEdge[]>([])
  const [selected, setSelected] = useState<GNode | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    if (first.data) { setNodes(first.data.nodes); setEdges(first.data.edges) }
  }, [first.data])

  const merge = useCallback((pic: KgPicture) => {
    setNodes((ns) => [...ns, ...pic.nodes.filter((n) => !ns.some((x) => x.id === n.id))])
    setEdges((es) => [...es, ...pic.edges.filter((e) => !es.some((x) => x.id === e.id))])
  }, [])

  const expand = async (n: Pick<GNode, 'set' | 'key'>) => {
    setBusy(true)
    setNote(null)
    try {
      const pic = await api.kgExpand(oid, n.set, n.key)
      const fresh = pic.nodes.filter((x) => !nodes.some((y) => y.id === x.id)).length
      merge(pic)
      setNote(fresh ? `Added ${fresh} connected record${fresh > 1 ? 's' : ''}.` : 'Everything it connects to is already shown.')
      return pic
    } catch (e) {
      setNote(describeError(e).message)
      return null
    } finally {
      setBusy(false)
    }
  }

  const colours = useMemo(() => {
    const things = [...new Set(nodes.map((n) => n.thing))]
    return new Map(things.map((t, i) => [t, PALETTE[i % PALETTE.length]]))
  }, [nodes])

  const flow = useMemo(() => {
    const pos = layout(nodes, edges)
    const fn: Node[] = nodes.map((n) => {
      const c = colours.get(n.thing) ?? '#747480'
      return {
        id: n.id, position: pos.get(n.id) ?? { x: 0, y: 0 },
        data: { label: n.label ?? n.key }, draggable: true,
        sourcePosition: Position.Right, targetPosition: Position.Left,   // lines run left to right
        className: `kgp-node${selected?.id === n.id ? ' is-selected' : ''}`,
        style: { borderLeft: `6px solid ${c}`, width: NODE_W },
      }
    })
    const fe: Edge[] = edges.map((e) => ({ id: e.id, source: e.source, target: e.target, type: 'default', className: 'flow-edge' }))
    return { fn, fe }
  }, [nodes, edges, colours, selected])

  if (first.initialLoading && !first.data) return <LoadingState label="Drawing the graph" />
  if (!first.data) return <p className="kgb__error">{describeError(first.error).message}</p>

  return (
    <section className="kgp" aria-label="The knowledge graph">
      <div className="kgp__bar">
        <div>
          <h2>Your knowledge graph</h2>
          <p className="kg-muted">A sample of real records to start. Click a point to see it; add its connections to grow the graph.</p>
        </div>
        <div className="kgp__find">
          <EntityPicker oid={oid} label="Find a record" placeholder="Find a record to add"
            onPick={async (h) => {
              const pic = await expand(h)
              const hit = pic?.nodes.find((x) => x.set === h.set && x.key === h.key)
              if (hit) setSelected(hit)
            }} />
        </div>
      </div>

      <div className="kgp__legend">
        {[...colours.entries()].map(([thing, c]) => (
          <span key={thing}><i style={{ background: c }} /> {thing}</span>
        ))}
        <span className="kg-muted">{nodes.length} records shown</span>
      </div>

      <div className="kgp__body">
        <div className="kgp__canvas">
          <ReactFlow nodes={flow.fn} edges={flow.fe} fitView fitViewOptions={{ padding: 0.15 }}
            minZoom={0.1} maxZoom={1.6} nodesConnectable={false}
            onNodeClick={(_, node) => setSelected(nodes.find((n) => n.id === node.id) ?? null)}>
            <Background gap={20} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        {selected ? (
          <RecordPanel oid={oid} node={selected} colour={colours.get(selected.thing)} busy={busy}
            onExpand={() => void expand(selected)} onClose={() => setSelected(null)} />
        ) : null}
      </div>
      {note ? <p className="kg-muted">{note}</p> : null}
    </section>
  )
}

function RecordPanel({ oid, node, colour, busy, onExpand, onClose }: {
  oid: string
  node: GNode
  colour?: string
  busy: boolean
  onExpand: () => void
  onClose: () => void
}) {
  const e = useAsync((signal) => api.kgEntity(oid, node.set, node.key, signal), [oid, node.set, node.key])
  return (
    <aside className="kgp__panel" aria-label="Record">
      <div className="kgp__panel-head">
        <span className="kgp__thing"><i style={{ background: colour }} /> {node.thing}</span>
        <button type="button" aria-label="Close" onClick={onClose}><X size={15} /></button>
      </div>
      <h3>{node.label ?? node.key}</h3>
      <Button size="sm" variant="primary" icon={<Plus size={14} />} loading={busy} onClick={onExpand}>
        Show its connections
      </Button>
      {e.data ? (
        <>
          <dl className="kgp__fields">
            {e.data.fields.slice(0, 10).map((f) => (
              <div key={f.column}>
                <dt>{f.label}</dt>
                <dd>{f.value === null || f.value === '' ? <span className="kg-muted">empty</span> : String(f.value)}
                  {f.personal ? <Lock size={11} aria-label="Personal data, masked" /> : null}</dd>
              </div>
            ))}
          </dl>
          <ul className="kgp__links">
            {e.data.connections.map((c, i) => (
              <li key={i}><span>{c.text}</span><strong>{c.direction === 'in' ? c.count : c.broken ? 'missing' : 1}</strong></li>
            ))}
          </ul>
        </>
      ) : <p className="kg-muted">Loading...</p>}
    </aside>
  )
}
