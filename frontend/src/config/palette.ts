/**
 * One colour per kind of thing, reused by the graph and the charts so a
 * colour means the same thing wherever it appears. Mirrors the backend class order
 * palette so the two views of the same data agree.
 */
export const CHART_PALETTE = [
  '#2272b4',
  '#067647',
  '#ff3621',
  '#7a5af8',
  '#0e7090',
  '#b54708',
  '#4e5ba6',
  '#d92d20',
  '#099250',
  '#6172f3',
] as const

export function colorFor(index: number): string {
  const safe = Number.isFinite(index) && index >= 0 ? Math.floor(index) : 0
  return CHART_PALETTE[safe % CHART_PALETTE.length] ?? CHART_PALETTE[0]
}
