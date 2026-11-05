/**
 * Pure helpers for the Ontology Accelerator screens: labels, tones and the
 * knowledge-map layout. Kept free of React so they are unit-tested.
 */
import type { BadgeTone } from '../components/Badge'
import type { EoMap, EoMapEdge, EoMapNode, EoStepStatus } from '../api/types'

export const STEP_STATUS: Record<EoStepStatus, { label: string; tone: BadgeTone }> = {
  done: { label: 'Done', tone: 'teal' },
  review: { label: 'Needs review', tone: 'amber' },
  ready: { label: 'Ready', tone: 'indigo' },
  waiting: { label: 'Waiting', tone: 'slate' },
}

const FINDINGS: Record<string, { title: string; tone: BadgeTone }> = {
  wrong_amount_column: { title: 'Report built on the wrong amount column', tone: 'rose' },
  mixed_currency_total: { title: 'Amounts added across currencies', tone: 'rose' },
  duplicate_golden_record: { title: 'Customer mastered twice', tone: 'amber' },
  duplicate_business_key: { title: 'Business key repeats', tone: 'amber' },
  stale_source: { title: 'Source behind its SLA', tone: 'amber' },
  corrections_not_in_sources: { title: 'Corrections never reached the sources', tone: 'amber' },
  name_contradicts_values: { title: 'Column name contradicts its data', tone: 'amber' },
}

export function findingInfo(type: string): { title: string; tone: BadgeTone } {
  return FINDINGS[type] ?? { title: type.replace(/_/g, ' '), tone: 'slate' }
}

/** Most serious first: rose before amber before the rest, then by type. */
export function sortFindings<T extends { type: string }>(findings: T[]): T[] {
  const rank = (t: string) => ({ rose: 0, amber: 1 } as Record<string, number>)[findingInfo(t).tone] ?? 2
  return [...findings].sort((a, b) => rank(a.type) - rank(b.type) || a.type.localeCompare(b.type))
}

export const METHOD_LABEL: Record<string, string> = {
  name: 'from the name',
  values: 'from the data',
  'values+name': 'name and data agree',
  reconciliation: 'reconciled with another system',
  steward: 'set by a steward',
}

export function methodLabel(method: string | undefined): string {
  return (method && METHOD_LABEL[method]) || method || 'unknown'
}

export const ROLE_LABEL: Record<string, string> = {
  source_system: 'Source system',
  mdm_hub: 'MDM hub',
  data_mart: 'Data mart',
  reference: 'Reference data',
}

/** net_amount, net_amount_usd, amount_unclassified: every money property. */
export function isMoneyProperty(property: string): boolean {
  return /(^|_)amount(_|$)/.test(property)
}

/** True when only the intake exists: no analysis step has produced anything. */
export function neverAnalysed(steps: Array<{ id: string; items: number }>): boolean {
  const analysis = steps.filter((s) => !['intake', 'govern', 'publish', 'drift'].includes(s.id))
  return analysis.length > 0 && analysis.every((s) => s.items === 0)
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(digits)}%`
}

/** Group items by a key, keeping first-seen order. */
export function groupBy<T>(items: T[], key: (item: T) => string): Array<[string, T[]]> {
  const out = new Map<string, T[]>()
  for (const item of items) {
    const k = key(item)
    const list = out.get(k)
    if (list) list.push(item)
    else out.set(k, [item])
  }
  return [...out.entries()]
}

// ------------------------------------------------------------ map layout
export interface PlacedNode extends EoMapNode {
  x: number
  y: number
  w: number
  h: number
}

export interface PlacedMap {
  nodes: PlacedNode[]
  edges: Array<EoMapEdge & { path: string; lx: number; ly: number }>
  width: number
  height: number
}

const COL_X = { table: 30, concept: 400, hierarchy: 860 }
const SIZE = { table: [260, 34], concept: [220, 54], hierarchy: [220, 40] } as const
const GAP = 14

/**
 * Three columns: source tables (grouped by source), concepts, drill paths.
 * Concepts sit at the average height of their tables, then are pushed apart
 * so none overlap; that keeps member lines short and mostly uncrossed.
 */
export function layoutMap(map: EoMap): PlacedMap {
  const tables = map.nodes.filter((n) => n.type === 'table')
    .sort((a, b) => (a.source ?? '').localeCompare(b.source ?? '') || a.label.localeCompare(b.label))
  const placed = new Map<string, PlacedNode>()
  let y = 20
  let lastSource: string | undefined
  for (const t of tables) {
    if (lastSource !== undefined && t.source !== lastSource) y += GAP
    lastSource = t.source
    const [w, h] = SIZE.table
    placed.set(t.id, { ...t, x: COL_X.table, y, w, h })
    y += h + GAP
  }
  const tablesBottom = y

  const concepts = map.nodes.filter((n) => n.type === 'concept')
  const wanted = concepts.map((c) => {
    const ys = map.edges.filter((e) => e.type === 'member' && e.to === c.id)
      .map((e) => placed.get(e.from)).filter(Boolean).map((n) => n!.y + n!.h / 2)
    return { c, at: ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : 0 }
  }).sort((a, b) => a.at - b.at || a.c.label.localeCompare(b.c.label))
  let floor = 20
  for (const { c, at } of wanted) {
    const [w, h] = SIZE.concept
    const top = Math.max(floor, at - h / 2)
    placed.set(c.id, { ...c, x: COL_X.concept, y: top, w, h })
    floor = top + h + GAP * 2
  }

  let hy = 20
  for (const n of map.nodes.filter((x) => x.type === 'hierarchy')) {
    const owner = map.edges.find((e) => e.type === 'hierarchy' && e.to === n.id)
    const anchor = owner ? placed.get(owner.from) : undefined
    const [w, h] = SIZE.hierarchy
    const top = Math.max(hy, anchor ? anchor.y + (anchor.h - h) / 2 : hy)
    placed.set(n.id, { ...n, x: COL_X.hierarchy, y: top, w, h })
    hy = top + h + GAP
  }

  const edges = map.edges.flatMap((e) => {
    const a = placed.get(e.from)
    const b = placed.get(e.to)
    if (!a || !b) return []
    if (e.type === 'relationship') {
      // Concept to concept: arc out to the right of the concept column.
      const x = a.x + a.w
      const ya = a.y + a.h / 2
      const yb = b.y + b.h / 2
      const bulge = 60 + Math.abs(yb - ya) * 0.25
      return [{ ...e, path: `M ${x} ${ya} C ${x + bulge} ${ya}, ${x + bulge} ${yb}, ${x} ${yb}`,
        lx: x + bulge * 0.78, ly: (ya + yb) / 2 }]
    }
    const x1 = a.x + a.w
    const y1 = a.y + a.h / 2
    const x2 = b.x
    const y2 = b.y + b.h / 2
    const mid = (x1 + x2) / 2
    return [{ ...e, path: `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`,
      lx: mid, ly: (y1 + y2) / 2 }]
  })

  const all = [...placed.values()]
  const height = Math.max(tablesBottom, ...all.map((n) => n.y + n.h + 20), 200)
  return { nodes: all, edges, width: COL_X.hierarchy + SIZE.hierarchy[0] + 30, height }
}
