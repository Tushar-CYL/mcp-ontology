import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, GraphChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import { cx } from '../utils/cx'

// Only the parts the product uses are registered, so the bundle stays sane.
echarts.use([
  BarChart,
  GraphChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

type ChartInstance = ReturnType<typeof echarts.init>
export type ChartOption = EChartsCoreOption
export type ChartEventHandler = (params: unknown) => void

interface EChartProps {
  option: ChartOption
  /** Describes the chart for screen readers and anyone not seeing it. */
  ariaLabel: string
  height?: number
  className?: string
  onEvents?: Record<string, ChartEventHandler>
  notMerge?: boolean
}

export function EChart({
  option,
  ariaLabel,
  height = 360,
  className,
  onEvents,
  notMerge = true,
}: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ChartInstance | null>(null)

  useEffect(() => {
    const element = containerRef.current
    if (!element) return

    const chart = echarts.init(element)
    chartRef.current = chart
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(element)

    return () => {
      observer.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge })
  }, [option, notMerge])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !onEvents) return
    const entries = Object.entries(onEvents)
    for (const [event, handler] of entries) {
      chart.on(event, handler)
    }
    return () => {
      for (const [event] of entries) {
        chart.off(event)
      }
    }
  }, [onEvents])

  return (
    <div
      ref={containerRef}
      className={cx('echart', className)}
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    />
  )
}
