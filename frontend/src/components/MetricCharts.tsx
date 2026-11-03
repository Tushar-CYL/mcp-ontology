import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { MetricSummary } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { formatValue } from '../utils/format'
import { Badge } from './Badge'
import { Card } from './Card'
import { EChart, type ChartOption } from './EChart'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'

const GRAINS = ['day', 'week', 'month', 'quarter', 'year'] as const
const INK = '#2e2e38'
const YELLOW = '#ffe600'
const GRID = '#ececf1'
const AXIS = '#696975'

export interface TrendPoint {
  period: string
  value: number | null
}

export interface BreakdownRow {
  key: string
  current: number | null
  prior: number | null
}

/** Monthly values from the governed definition. */
export function TrendChart({ points, label, height = 240 }: {
  points: TrendPoint[]
  label: string
  height?: number
}) {
  const option = useMemo<ChartOption>(() => ({
    animationDuration: 400,
    tooltip: { trigger: 'axis', confine: true },
    grid: { left: 70, right: 20, top: 16, bottom: 36 },
    xAxis: {
      type: 'category',
      data: points.map((p) => p.period.slice(0, 7)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: GRID } },
      axisLabel: { color: AXIS, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: GRID } },
      axisLabel: { color: AXIS, fontSize: 11 },
    },
    series: [{
      type: 'line',
      data: points.map((p) => p.value),
      symbolSize: 7,
      lineStyle: { color: INK, width: 2 },
      itemStyle: { color: YELLOW, borderColor: INK, borderWidth: 1.5 },
      areaStyle: { color: 'rgba(255,230,0,0.12)' },
    }],
  }), [points])
  if (points.length === 0) return <p className="muted">This metric has no dated values to chart.</p>
  return <EChart option={option} height={height} ariaLabel={`Monthly trend of ${label}`} />
}

/** Current vs prior period for each value of one dimension. */
export function BreakdownChart({ rows, dimension, label, height = 260 }: {
  rows: BreakdownRow[]
  dimension: string
  label: string
  height?: number
}) {
  const top = rows.slice(0, 12)
  const option = useMemo<ChartOption>(() => ({
    animationDuration: 400,
    tooltip: { trigger: 'axis', confine: true },
    legend: { data: ['Previous period', 'This period'], top: 0, textStyle: { color: AXIS } },
    grid: { left: 70, right: 20, top: 34, bottom: 56 },
    xAxis: {
      type: 'category',
      data: top.map((r) => r.key),
      axisLabel: { color: AXIS, fontSize: 11, rotate: top.length > 6 ? 30 : 0 },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: GRID } },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: GRID } }, axisLabel: { color: AXIS, fontSize: 11 } },
    series: [
      { name: 'Previous period', type: 'bar', data: top.map((r) => r.prior), itemStyle: { color: '#c4c4cd' } },
      { name: 'This period', type: 'bar', data: top.map((r) => r.current), itemStyle: { color: INK } },
    ],
  }), [top])
  if (top.length === 0) return <p className="muted">No breakdown for this period.</p>
  return <EChart option={option} height={height} ariaLabel={`${label} by ${dimension}`} />
}

/**
 * The Semantic page's charts for one metric: the monthly trend and the
 * latest change split by the metric's first dimension. A proposed (draft)
 * metric is previewed, never served.
 */
export function MetricCharts({ source, metric }: { source: string; metric: MetricSummary }) {
  const draft = metric.status === 'draft'
  // Undefined = let the server choose the grain from the data's own span.
  const [grain, setGrain] = useState<string | undefined>(undefined)
  const insights = useAsync(
    (signal) => api.metricInsights(metric.name, { source, previewDraft: draft, grain }, signal),
    [source, metric.name, draft, grain],
  )
  const data = insights.data
  const breakdown: BreakdownRow[] = (data?.contributors ?? []).map((c) => ({
    key: c.key, current: c.value, prior: c.prior,
  }))
  const last = data?.trend.at(-1)
  return (
    <Card
      title="What the data shows"
      subtitle={`Every point is computed from the ${draft ? 'proposed' : 'approved'} definition, on the full data.`}
      actions={draft ? <Badge tone="amber" dot>Preview of a proposal</Badge> : null}
    >
      {insights.loading && !data ? <LoadingState label="Computing from the data" compact /> : null}
      {insights.error ? <ErrorState error={insights.error} compact /> : null}
      {data ? (
        <div className="metric-charts">
          <div>
            <div className="chart-head">
              <p className="chart-title">
                Trend by {data.grain ?? 'month'}
                {last ? ` · latest ${last.period.slice(0, 10)}: ${formatValue(last.value)}` : ''}
              </p>
              <div className="grain-switch" role="group" aria-label="Time grain">
                {GRAINS.map((g) => (
                  <button
                    key={g}
                    type="button"
                    className={(data.grain ?? 'month') === g ? 'grain grain--active' : 'grain'}
                    onClick={() => setGrain(g)}
                    aria-pressed={(data.grain ?? 'month') === g}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>
            {data.time_range?.min ? (
              <p className="muted chart-range">
                Data from {data.time_range.min} to {data.time_range.max}
                {grain ? '' : ' · grain chosen from that span'}
              </p>
            ) : null}
            <TrendChart points={data.trend} label={metric.title} />
          </div>
          {data.dimension ? (
            <div>
              <p className="chart-title">By {data.dimension.toLowerCase()} · latest period vs the one before</p>
              <BreakdownChart rows={breakdown} dimension={data.dimension} label={metric.title} />
            </div>
          ) : null}
        </div>
      ) : null}
    </Card>
  )
}
