import dagre from '@dagrejs/dagre'
import type { BadgeTone } from '../components/Badge'
import type { OntoCheck, OntoField, OntoLink, OntoSetBy, OntoSummary, OntoThing } from '../api/types'

/** How each data check reads on screen. */
export const CHECK: Record<OntoCheck, { label: string; tone: BadgeTone; hint: string }> = {
  verified: { label: 'Checked in data', tone: 'teal',
    hint: 'The data agrees with this meaning.' },
  conflict: { label: 'Data disagrees', tone: 'rose',
    hint: 'The AI suggested something the data contradicts; the data\'s answer is shown.' },
  unchecked: { label: 'Not checked', tone: 'slate',
    hint: 'Nothing in the data can confirm or deny this.' },
}

export const SET_BY: Record<OntoSetBy, string> = {
  you: 'You',
  metadata: 'Your metadata',
  ai: 'AI',
  engine: 'Engine',
}

/** Share of fields the data confirmed, as a whole percentage. */
export function checkedShare(summary: OntoSummary): number {
  const total = summary.fields
  if (!total) return 0
  return Math.round((100 * (summary.checks.verified ?? 0)) / total)
}

/** Search and the "only problems" switch, for one thing's fields. */
export function filterFields(fields: OntoField[], query: string, onlyConflicts: boolean): OntoField[] {
  const q = query.trim().toLowerCase()
  return fields.filter((f) => {
    if (onlyConflicts && f.check !== 'conflict') return false
    if (!q) return true
    return [f.label, f.column, f.meaning, f.role_label, f.unit ?? '']
      .some((text) => text.toLowerCase().includes(q))
  })
}

/** Things matching a search over their name, description and field labels. */
export function filterThings(things: OntoThing[], query: string): OntoThing[] {
  const q = query.trim().toLowerCase()
  if (!q) return things
  return things.filter((t) => t.name.toLowerCase().includes(q)
    || t.description.toLowerCase().includes(q)
    || t.fields.some((f) => f.label.toLowerCase().includes(q) || f.column.toLowerCase().includes(q)))
}

/** The thing to open first: the most linked one, then the one with most fields. */
export function centralThing(view: { things: OntoThing[]; links: OntoLink[] }): string | undefined {
  const degree = new Map<string, number>()
  for (const l of view.links) {
    degree.set(l.from_thing, (degree.get(l.from_thing) ?? 0) + 1)
    degree.set(l.to_thing, (degree.get(l.to_thing) ?? 0) + 1)
  }
  return [...view.things].sort((a, b) => (degree.get(b.name) ?? 0) - (degree.get(a.name) ?? 0)
    || b.fields.length - a.fields.length || a.name.localeCompare(b.name))[0]?.name
}

export function conflictCount(thing: OntoThing): number {
  return thing.fields.filter((f) => f.check === 'conflict').length
}

export function formatCount(n: number): string {
  return n.toLocaleString('en-US')
}

export function matchLabel(match: number | null | undefined): string {
  if (typeof match !== 'number') return ''
  return `${Math.round(match * 100)}% match`
}

/** Short tag for where an ontology came from. */
export function sourceLine(sources: string[], metadata: string[]): string {
  const parts: string[] = []
  if (sources.length) parts.push(`${sources.length} data source${sources.length > 1 ? 's' : ''}`)
  if (metadata.length) parts.push(`${metadata.length} metadata file${metadata.length > 1 ? 's' : ''}`)
  return parts.join(' + ') || 'nothing connected'
}

export const NODE_W = 230
export const NODE_H = 96

// A type alias (not an interface) so it satisfies React Flow's
// Record<string, unknown> constraint on node data.
export type FlowNodeData = {
  name: string
  fields: number
  records: number
  keys: string[]
  conflicts: number
}

/**
 * Positions for the map, laid out by dagre: "many" things on the left, the
 * thing they belong to on the right, so every arrow reads left to right.
 * Things with no link are placed in a row underneath.
 */
export function flowLayout(things: OntoThing[], links: OntoLink[]): {
  nodes: Array<{ id: string; x: number; y: number; data: FlowNodeData }>
  edges: Array<{ id: string; source: string; target: string; label: string; directed: boolean }>
  dense: boolean
} {
  const names = new Set(things.map((t) => t.name))
  // One line per pair of things: a knowledge graph can have dozens of
  // relations between the same two types, which would be unreadable.
  const pairs = new Map<string, { source: string; target: string; labels: string[] }>()
  for (const l of links) {
    if (!names.has(l.from_thing) || !names.has(l.to_thing) || l.from_thing === l.to_thing) continue
    const id = `${l.from_thing}->${l.to_thing}`
    const label = l.verb ?? (l.cardinality === 'one-to-one' ? 'has one' : 'belongs to')
    const pair = pairs.get(id) ?? { source: l.from_thing, target: l.to_thing, labels: [] }
    if (!pair.labels.includes(label)) pair.labels.push(label)
    pairs.set(id, pair)
  }
  let edges = [...pairs.entries()].map(([id, p]) => ({ id, source: p.source, target: p.target,
    label: p.labels.length > 1 ? `${p.labels.length} relations` : p.labels[0], directed: true }))
  const linked = new Set(edges.flatMap((e) => [e.source, e.target]))
  const data = (t: OntoThing): FlowNodeData => ({
    name: t.name, fields: t.fields.length, records: t.records,
    keys: t.fields.filter((f) => f.role === 'identifier').map((f) => f.label).slice(0, 2),
    conflicts: conflictCount(t),
  })

  // A dense graph (most things link to most others, both ways: a knowledge
  // graph) cannot be read as a left-to-right flow. Put the things on a circle
  // and draw one line per pair, both directions together.
  if (linked.size > 3 && edges.length > linked.size * 1.5) {
    const both = new Map<string, { source: string; target: string; count: number; labels: string[] }>()
    for (const p of pairs.values()) {
      const [a, b] = [p.source, p.target].sort()
      const id = `${a}<->${b}`
      const e = both.get(id) ?? { source: a, target: b, count: 0, labels: [] }
      e.count += p.labels.length
      e.labels.push(...p.labels.filter((x) => !e.labels.includes(x)))
      both.set(id, e)
    }
    edges = [...both.entries()].map(([id, e]) => ({ id, source: e.source, target: e.target,
      label: e.count > 1 ? `${e.count} relations` : e.labels[0], directed: false }))
    const ring = things.filter((t) => linked.has(t.name))
    const r = Math.max(380, (ring.length * (NODE_W + 120)) / (2 * Math.PI))
    const nodes = ring.map((t, i) => {
      const angle = (2 * Math.PI * i) / ring.length - Math.PI / 2
      return { id: t.name, x: Math.round(r + 1.15 * r * Math.cos(angle)), y: Math.round(r * 0.8
        + r * 0.8 * Math.sin(angle)), data: data(t) }
    })
    things.filter((t) => !linked.has(t.name)).forEach((t, i) => {
      nodes.push({ id: t.name, x: i * (NODE_W + 36), y: Math.round(r * 1.5) + NODE_H + 60, data: data(t) })
    })
    return { nodes, edges, dense: true }
  }

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 36, ranksep: 120, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const t of things) if (linked.has(t.name)) g.setNode(t.name, { width: NODE_W, height: NODE_H })
  for (const e of edges) g.setEdge(e.source, e.target)
  dagre.layout(g)
  let maxY = 0
  const nodes: Array<{ id: string; x: number; y: number; data: FlowNodeData }> = []
  for (const t of things) {
    if (!linked.has(t.name)) continue
    const n = g.node(t.name)
    maxY = Math.max(maxY, n.y + NODE_H / 2)
    nodes.push({ id: t.name, x: n.x - NODE_W / 2, y: n.y - NODE_H / 2, data: data(t) })
  }
  things.filter((t) => !linked.has(t.name)).forEach((t, i) => {
    nodes.push({ id: t.name, x: 20 + (i % 4) * (NODE_W + 36), y: (linked.size ? maxY + 60 : 20)
      + Math.floor(i / 4) * (NODE_H + 36), data: data(t) })
  })
  return { nodes, edges, dense: false }
}

/** "3 minutes ago", for the header. */
export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return ''
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (s < 60) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} hour${h === 1 ? '' : 's'} ago`
  const d = Math.round(h / 24)
  return `${d} day${d === 1 ? '' : 's'} ago`
}
