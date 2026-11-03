/**
 * One colour per kind of thing, reused by the graph and the charts so a
 * colour means the same thing wherever it appears. Mirrors the backend class order
 * palette so the two views of the same data agree.
 */
export const CHART_PALETTE = [
  '#188ce5', // EY blue
  '#2db757', // EY green
  '#ff6d00', // EY orange
  '#724bc3', // EY purple
  '#27acaa', // EY teal
  '#ff4136', // EY red
  '#750e5c', // EY maroon
  '#3d108a', // EY deep purple
  '#168736', // EY deep green
  '#747480', // EY grey
] as const

export function colorFor(index: number): string {
  const safe = Number.isFinite(index) && index >= 0 ? Math.floor(index) : 0
  return CHART_PALETTE[safe % CHART_PALETTE.length] ?? CHART_PALETTE[0]
}
