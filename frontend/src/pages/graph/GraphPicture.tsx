import { useCallback, useEffect, useMemo, useState } from 'react'
import { Background, Controls, Position, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import { ChevronDown, ChevronRight, Globe2, Lock, Plus, Route, Share2, Workflow, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { KgConnectionPage, KgEntity, KgGlobe, KgOverview, KgPath, KgPicture } from '../../api/types'
import { Button } from '../../components/Button'
import { LoadingState } from '../../components/LoadingState'
import { useAsync } from '../../hooks/useAsync'
import { EntityPicker } from './EntityPicker'
import { ExploreCanvas } from './ExploreGraph'
import { GlobeGraph } from './GlobeGraph'

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
type View = 'globes' | 'flow' | 'explore'
const VIEWS: Array<{ id: View; label: string; icon: typeof Globe2; hint: string }> = [
  { id: 'globes', label: 'Globes', icon: Globe2, hint: 'One globe per kind of thing, its records inside' },
  { id: 'flow', label: 'Record by record', icon: Workflow, hint: 'A few records, their links left to right' },
  { id: 'explore', label: 'Connections', icon: Share2, hint: 'Business terms or source tables as linked bubbles' },
]

export function GraphPicture({ oid, overview }: { oid: string; overview?: KgOverview | null }) {
  const [view, setView] = useState<View>('globes')
  const globe = useAsync<KgGlobe>((signal) => api.kgGlobe(oid, signal), [oid])
  const first = useAsync((signal) => api.kgSample(oid, signal), [oid])
  const [gNodes, setGNodes] = useState<GNode[]>([])
  const [gEdges, setGEdges] = useState<GEdge[]>([])
  const [fNodes, setFNodes] = useState<GNode[]>([])
  const [fEdges, setFEdges] = useState<GEdge[]>([])
  const isExplore = view === 'explore'
  const isGlobe = view === 'globes'
  const nodes = isGlobe ? gNodes : fNodes
  const edges = isGlobe ? gEdges : fEdges
  const setNodes = isGlobe ? setGNodes : setFNodes
  const setEdges = isGlobe ? setGEdges : setFEdges
  const [selected, setSelected] = useState<GNode | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    if (first.data) { setFNodes(first.data.nodes); setFEdges(first.data.edges) }
  }, [first.data])
  useEffect(() => {
    if (globe.data) { setGNodes(globe.data.nodes); setGEdges(globe.data.edges) }
  }, [globe.data])

  const merge = useCallback((pic: KgPicture) => {
    setNodes((ns) => [...ns, ...pic.nodes.filter((n) => !ns.some((x) => x.id === n.id))])
    setEdges((es) => [...es, ...pic.edges.filter((e) => !es.some((x) => x.id === e.id))])
  }, [setNodes, setEdges])

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

  // The same colour for a kind of thing in every view: biggest kinds first.
  const order = useMemo(() => {
    const ranked = (globe.data?.things ?? []).map((t) => t.thing)
    const rest = [...new Set([...gNodes, ...fNodes].map((n) => n.thing))].filter((t) => !ranked.includes(t))
    return [...ranked, ...rest.sort()]
  }, [globe.data, gNodes, fNodes])
  const colours = useMemo(() => new Map(order.map((t, i) => [t, PALETTE[i % PALETTE.length]])), [order])
  const totals = useMemo(() => new Map((globe.data?.things ?? []).map((t) => [t.thing, t.records])), [globe.data])

  const flow = useMemo(() => {
    const pos = layout(nodes, edges)
    const fn: Node[] = nodes.map((n) => {
      const c = colours.get(n.thing) ?? '#747480'
      return {
        id: n.id, position: pos.get(n.id) ?? { x: 0, y: 0 },
        data: { label: n.label ?? n.key }, draggable: true,
        sourcePosition: Position.Right, targetPosition: Position.Left,   // lines run left to right
        className: `kgp-node${selected?.id === n.id ? ' is-selected' : ''}`,
        style: {
          borderLeft: `4px solid ${c}`,
          width: NODE_W,
          background: '#18181b',
          border: '1px solid #3f3f46',
          borderLeftWidth: 4,
          borderLeftColor: c,
          color: '#fafafa',
          borderRadius: 10,
          fontSize: 12,
          boxShadow: '0 4px 14px rgba(0,0,0,0.35)',
        },
      }
    })
    const fe: Edge[] = edges.map((e) => ({
      id: e.id, source: e.source, target: e.target, type: 'default', className: 'kgp-edge',
      style: { stroke: '#71717a', strokeWidth: 1.5 },
    }))
    return { fn, fe }
  }, [nodes, edges, colours, selected])

  const source = isExplore ? null : isGlobe ? globe : first
  if (source?.initialLoading && !source.data) return <LoadingState label="Drawing the graph" />
  if (source && !source.data) return <p className="kgb__error">{describeError(source.error).message}</p>
  if (isExplore && !overview) return <LoadingState label="Drawing the graph" />
  const kinds = new Set(nodes.map((n) => n.thing)).size
  const blurb = isExplore
    ? 'Business terms or source tables as linked bubbles. Switch Terms / Tables on the canvas.'
    : isGlobe
      ? `${kinds} kinds · ${nodes.length} records · ${edges.length} links — each globe is one kind of thing`
      : 'A few records and their links, left to right. Click a point to open it; grow from there.'

  return (
    <section className="kgp" aria-label="The knowledge graph">
      <div className="kgp__bar">
        <div className="kgp__bar-start">
          <h2>The dot picture</h2>
          <p className="kg-muted">{blurb}</p>
        </div>
        <div className="kgp__views" role="tablist" aria-label="How to draw the graph">
          {VIEWS.map((v) => {
            const Icon = v.icon
            return (
              <button key={v.id} type="button" role="tab" aria-selected={view === v.id} title={v.hint}
                className={view === v.id ? 'is-on' : undefined}
                onClick={() => { setView(v.id); setSelected(null); setNote(null) }}>
                <Icon size={14} aria-hidden="true" /> {v.label}
              </button>
            )
          })}
        </div>
        <div className="kgp__bar-end">
          {!isExplore ? (
            <div className="kgp__find">
              <EntityPicker oid={oid} label="Find a record" placeholder="Find a record to add"
                onPick={async (h) => {
                  const pic = await expand(h)
                  const hit = pic?.nodes.find((x) => x.set === h.set && x.key === h.key)
                  if (hit) setSelected(hit)
                }} />
            </div>
          ) : null}
        </div>
      </div>

      {!isExplore ? (
        <div className="kgp__legend">
          {[...colours.entries()].map(([thing, c]) => (
            <span key={thing}><i style={{ background: c }} /> {thing}</span>
          ))}
          <span className="kg-muted">{nodes.length} records shown{isGlobe && totals.size
            ? ` of ${[...totals.values()].reduce((a, b) => a + b, 0).toLocaleString()}` : ''}</span>
        </div>
      ) : null}

      <div className="kgp__body">
        {isExplore && overview ? (
          <div className="kgp__canvas kgp__canvas--globe kgp__canvas--explore">
            <ExploreCanvas overview={overview} />
          </div>
        ) : isGlobe ? (
          <div className="kgp__canvas kgp__canvas--globe">
            <GlobeGraph nodes={gNodes} edges={gEdges} colours={colours} order={order} totals={totals}
              mode="globes" selected={selected?.id ?? null}
              onSelect={(id) => setSelected(gNodes.find((n) => n.id === id) ?? null)} />
          </div>
        ) : (
        <div className="kgp__canvas kgp__canvas--flow">
          <ReactFlow nodes={flow.fn} edges={flow.fe} fitView fitViewOptions={{ padding: 0.18 }}
            minZoom={0.1} maxZoom={1.6} nodesConnectable={false} colorMode="dark"
            proOptions={{ hideAttribution: true }}
            onNodeClick={(_, node) => setSelected(nodes.find((n) => n.id === node.id) ?? null)}>
            <Background gap={22} size={1} color="#3f3f46" />
            <Controls showInteractive={false} className="kgp__controls" />
          </ReactFlow>
        </div>
        )}
        {!isExplore && selected ? (
          <RecordPanel oid={oid} node={selected} colour={colours.get(selected.thing)} busy={busy}
            onExpand={() => void expand(selected)} onClose={() => setSelected(null)}
            onOpen={async (ref) => {
              const pic = await expand(ref)
              const hit = pic?.nodes.find((x) => x.set === ref.set && x.key === ref.key)
              if (hit) setSelected(hit)
            }}
            onPath={(path) => {
              const steps = path.steps ?? []
              const pn: GNode[] = steps.map((st) => ({ id: `${st.set}|${st.key}`, set: st.set, key: st.key,
                thing: st.thing, label: st.label }))
              const pe: GEdge[] = steps.slice(1).map((st, i) => ({ id: `path:${pn[i].id}->${pn[i + 1].id}`,
                source: pn[i].id, target: pn[i + 1].id, label: st.via ?? '' }))
              merge({ nodes: pn, edges: pe })
              setNote(`Path drawn: ${steps.length - 1} step${steps.length === 2 ? '' : 's'}.`)
            }} />
        ) : null}
      </div>
      {note ? <p className="kg-muted">{note}</p> : null}
    </section>
  )
}

function RecordPanel({ oid, node, colour, busy, onExpand, onClose, onOpen, onPath }: {
  oid: string
  node: GNode
  colour?: string
  busy: boolean
  onExpand: () => void
  onClose: () => void
  onOpen: (ref: { set: string; key: string }) => void
  onPath: (path: KgPath) => void
}) {
  const e = useAsync((signal) => api.kgEntity(oid, node.set, node.key, signal), [oid, node.set, node.key])
  const [open, setOpen] = useState<string | null>(null)
  const [path, setPath] = useState<KgPath | null>(null)
  const [pathBusy, setPathBusy] = useState(false)
  const [pathError, setPathError] = useState<string | null>(null)
  const findPath = async (to: { set: string; key: string }) => {
    setPathBusy(true)
    setPathError(null)
    try {
      const found = await api.kgPath(oid, { set: node.set, key: node.key }, to, 6)
      setPath(found)
      if (found.found) onPath(found)
    } catch (err) {
      setPathError(describeError(err).message)
    } finally {
      setPathBusy(false)
    }
  }
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
          <p className="kgp__hint">Linked records, by kind of link. Open one to see them all.</p>
          <ul className="kgp__links">
            {e.data.connections.map((c) => {
              const id = `${c.direction}:${c.link}`
              const count = c.direction === 'in' ? c.count : c.broken ? 0 : 1
              const isOpen = open === id
              return (
                <li key={id} className={isOpen ? 'is-open' : undefined}>
                  <button type="button" className="kgp__link" aria-expanded={isOpen} disabled={!count}
                    onClick={() => setOpen(isOpen ? null : id)}>
                    {isOpen ? <ChevronDown size={13} aria-hidden="true" /> : <ChevronRight size={13} aria-hidden="true" />}
                    <span>{c.text}</span>
                    <strong>{c.direction === 'out' && c.broken ? 'missing' : count.toLocaleString('en-US')}</strong>
                  </button>
                  {isOpen && e.data ? <Linked oid={oid} entity={e.data} c={c} onOpen={onOpen} /> : null}
                </li>
              )
            })}
          </ul>
          <div className="kgp__path">
            <span className="kgp__hint"><Route size={13} aria-hidden="true" /> How is it connected to…</span>
            <EntityPicker oid={oid} label="Connected to" placeholder="Another record, by id or name"
              onPick={(h) => void findPath(h)} />
            {pathBusy ? <p className="kg-muted">Following the links…</p> : null}
            {pathError ? <p className="kgb__error">{pathError}</p> : null}
            {path && !pathBusy ? (
              path.found && path.steps ? (
                <ol className="kgp__chain">
                  {path.steps.map((st, i) => (
                    <li key={`${st.set}|${st.key}`}>
                      {i > 0 && st.via ? <span className="kg-muted">{st.via}</span> : null}
                      <button type="button" onClick={() => onOpen(st)}>{st.thing}: {st.label ?? st.key}</button>
                    </li>
                  ))}
                </ol>
              ) : <p className="kg-muted">{path.text ?? 'No chain of proven links joins them.'}</p>
            ) : null}
          </div>
        </>
      ) : <p className="kg-muted">Loading...</p>}
    </aside>
  )
}

/** Drill-down: the records linked through one link, 25 at a time, narrowed by a word. */
function Linked({ oid, entity, c, onOpen }: {
  oid: string
  entity: KgEntity
  c: KgEntity['connections'][number]
  onOpen: (ref: { set: string; key: string }) => void
}) {
  // Graph sources (RDF / triples) list their first few, as before.
  const graphOnly = entity.set.startsWith('graph:')
  const [q, setQ] = useState('')
  const [pages, setPages] = useState<KgConnectionPage[]>([])
  const [loading, setLoading] = useState(!graphOnly)
  const [err, setErr] = useState<string | null>(null)
  const load = useCallback(async (offset: number, word: string) => {
    setLoading(true)
    setErr(null)
    try {
      const page = await api.kgConnection(oid, entity.set, entity.key, c.link, offset, word)
      setPages((ps) => (offset ? [...ps, page] : [page]))
    } catch (e) {
      setErr(describeError(e).message)
    } finally {
      setLoading(false)
    }
  }, [oid, entity.set, entity.key, c.link])
  useEffect(() => {
    if (graphOnly) return undefined
    const t = setTimeout(() => void load(0, q), q ? 300 : 0)
    return () => clearTimeout(t)
  }, [graphOnly, load, q])
  const items = graphOnly ? c.items : pages.flatMap((p) => p.items)
  const last = pages[pages.length - 1]
  const matching = last ? last.matching : c.count
  return (
    <div className="kgp__drill">
      {!graphOnly && c.count > 10 ? (
        <input className="input" value={q} placeholder={`Find one of the ${c.count.toLocaleString('en-US')}`}
          aria-label="Find a linked record" onChange={(ev) => setQ(ev.target.value)} />
      ) : null}
      {err ? <p className="kgb__error">{err}</p> : null}
      <ul>
        {items.map((it) => (
          <li key={`${it.set}|${it.key}`}>
            <button type="button" onClick={() => onOpen(it)} title="Add to the picture and open it">
              {it.label ?? it.key}
            </button>
          </li>
        ))}
      </ul>
      {loading ? <p className="kg-muted">Loading…</p> : null}
      {!graphOnly && !loading && items.length < matching ? (
        <Button size="sm" variant="ghost" onClick={() => void load(items.length, q)}>
          Show more ({(matching - items.length).toLocaleString('en-US')} left)
        </Button>
      ) : null}
      {!graphOnly && !loading && q && !matching ? <p className="kg-muted">None match “{q}”.</p> : null}
    </div>
  )
}
