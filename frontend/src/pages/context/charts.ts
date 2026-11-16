import type { ChartOption } from '../../components/EChart'

/** Reference categorical palette, slot 1 (one series = one colour, no legend). */
export const SERIES_1 = '#2a78d6'
const INK_MUTED = '#6b6a66'
const GRID = '#e8e7e2'

export type Shape =
  | { kind: 'number'; value: number | string; label: string }
  | { kind: 'bar' | 'line'; x: string[]; y: number[]; xLabel: string; yLabel: string; horizontal: boolean }
  | { kind: 'table' }

const isNumber = (v: unknown) => typeof v === 'number' && Number.isFinite(v)
const looksLikeTime = (v: unknown) => /^\d{4}-\d{2}(-\d{2})?([ T].*)?$/.test(String(v ?? ''))

/**
 * Which picture answers a result table:
 * one value -> a big number; a time column + a number -> a line;
 * a label + a number -> bars (horizontal when labels are long or many);
 * anything else -> just the table. Only ONE number column is ever drawn
 * (one axis); the table keeps the rest.
 */
export function shapeOf(columns: string[], rows: Array<Array<unknown>>): Shape {
  if (!rows.length || !columns.length) return { kind: 'table' }
  if (rows.length === 1 && columns.length === 1) {
    return { kind: 'number', value: rows[0][0] as number | string, label: columns[0] }
  }
  const numCol = columns.findIndex((_, i) => rows.every((r) => r[i] === null || isNumber(r[i])))
  const labelCol = columns.findIndex((_, i) => i !== numCol && rows.some((r) => !isNumber(r[i])))
  if (numCol < 0) return { kind: 'table' }
  if (rows.length === 1 && labelCol < 0) {
    return { kind: 'number', value: rows[0][numCol] as number, label: columns[numCol] }
  }
  if (labelCol < 0 || rows.length < 2) return { kind: 'table' }
  const x = rows.map((r) => String(r[labelCol] ?? '(empty)'))
  const y = rows.map((r) => Number(r[numCol] ?? 0))
  const time = rows.every((r) => looksLikeTime(r[labelCol]))
  const longLabels = x.some((s) => s.length > 14) || x.length > 8
  return {
    kind: time ? 'line' : 'bar', x, y, xLabel: columns[labelCol], yLabel: columns[numCol],
    horizontal: !time && longLabels,
  }
}

export function compact(n: number): string {
  if (!Number.isFinite(n)) return String(n)
  const abs = Math.abs(n)
  if (abs >= 1e9) return `${(n / 1e9).toFixed(1).replace(/\.0$/, '')}B`
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`
  if (abs >= 1e4) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}k`
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

/** ECharts option for one series: thin marks, 4px rounded data end,
 *  recessive grid, axis tooltip. */
export function chartOption(kind: 'bar' | 'line', x: string[], y: number[], yLabel: string,
  horizontal = false): ChartOption {
  const cat = { type: 'category', data: horizontal ? [...x].reverse() : x,
    axisLine: { lineStyle: { color: GRID } }, axisTick: { show: false },
    axisLabel: { color: INK_MUTED, fontSize: 11, hideOverlap: true,
      formatter: (v: string) => (v.length > 22 ? `${v.slice(0, 21)}…` : v) } }
  const val = { type: 'value', splitLine: { lineStyle: { color: GRID } },
    axisLabel: { color: INK_MUTED, fontSize: 11, formatter: (v: number) => compact(v) } }
  const data = horizontal ? [...y].reverse() : y
  return {
    animationDuration: 400,
    grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis', axisPointer: { type: kind === 'line' ? 'line' : 'shadow' },
      valueFormatter: (v: number) => `${compact(Number(v))} ${yLabel}`,
    },
    xAxis: horizontal ? val : cat,
    yAxis: horizontal ? cat : val,
    series: [kind === 'line'
      ? { type: 'line', data, showSymbol: false, symbolSize: 8, lineStyle: { width: 2, color: SERIES_1 },
          itemStyle: { color: SERIES_1 }, areaStyle: { color: 'rgba(42,120,214,0.08)' } }
      : { type: 'bar', data, barMaxWidth: 26, itemStyle: { color: SERIES_1,
          borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] } }],
  }
}

/**
 * The one-line answer for a chart, written from the numbers themselves (the
 * chart shows the rest): the biggest and its share for bars, the latest and
 * the peak for a line.
 */
export function headline(shape: Shape): string | null {
  if (shape.kind !== 'bar' && shape.kind !== 'line') return null
  const { x, y } = shape
  if (!y.length) return null
  const total = y.reduce((a, b) => a + b, 0)
  if (shape.kind === 'line') {
    const peak = y.indexOf(Math.max(...y))
    return `${compact(y[y.length - 1])} in ${x[x.length - 1]}; the peak was ${compact(y[peak])} in ${x[peak]}.`
  }
  const top = y.indexOf(Math.max(...y))
  const share = total > 0 ? Math.round((100 * y[top]) / total) : 0
  return `${x[top]} is the largest: ${compact(y[top])}${total > 0 && y.length > 1 ? `, ${share}% of ${compact(total)}` : ''}.`
}

/** A tiny trend line for a metric card: no axes, no labels, hover shows values. */
export function sparkOption(points: Array<{ period: string; value: number | null }>): ChartOption {
  return {
    animation: false,
    grid: { left: 2, right: 2, top: 4, bottom: 2 },
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => compact(Number(v)) },
    xAxis: { type: 'category', show: false, data: points.map((p) => p.period.slice(0, 7)) },
    yAxis: { type: 'value', show: false, scale: true },
    series: [{ type: 'line', data: points.map((p) => p.value), showSymbol: false,
      lineStyle: { width: 2, color: SERIES_1 }, areaStyle: { color: 'rgba(42,120,214,0.08)' } }],
  }
}

