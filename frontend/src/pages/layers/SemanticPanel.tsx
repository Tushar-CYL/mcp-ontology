import { useEffect, useMemo, useRef, useState } from 'react'
import { ChartColumn, Copy, Play, RefreshCw, ShieldCheck, Square, Table2 } from 'lucide-react'
import { api, isAbortError, describeError } from '../../api/client'
import type {
  EvaluateMetricRequest,
  EvaluateMetricResponse,
  MetricHealthResponse,
  MetricRow,
  MetricSummary,
  SourceSummary,
} from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { EChart, type ChartOption } from '../../components/EChart'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { TextInput } from '../../components/Field'
import { JsonView } from '../../components/JsonView'
import { LoadingState } from '../../components/LoadingState'
import { NoSourceState } from '../../components/NoSourceState'
import { Table, type Column } from '../../components/Table'
import { useSource } from '../../context/SourceContext'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { copyText } from '../../utils/download'
import { formatValue, humanize, truncate } from '../../utils/format'
import { statusLabel, statusTone } from '../../utils/status'
import { cx } from '../../utils/cx'
import { MetricUsageBadge, SqlValidator } from '../../components/SqlValidator'
import { MetricCharts } from '../../components/MetricCharts'
import { SynonymsEditor } from '../../components/SynonymsEditor'

export function SemanticPanel() {
  useDocumentTitle('Semantic')
  const { selectedSource, loading } = useSource()

  if (loading && !selectedSource) return <LoadingState label="Loading sources" />
  if (!selectedSource) return <NoSourceState />
  return <SemanticView key={selectedSource.id} source={selectedSource} />
}

interface NormalizedMetric {
  columns: Array<{ key: string; label: string }>
  rows: Array<Record<string, unknown>>
  labels: string[]
  values: number[]
  singleValue: unknown
  hasGroup: boolean
}

function toNumberOrZero(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : 0
}

function normalizeMetricRows(rows: MetricRow[], groupBy: string): NormalizedMetric | null {
  if (!rows || rows.length === 0) return null
  const first = rows[0]
  const hasGroup = Boolean(groupBy.trim())

  if (Array.isArray(first)) {
    const width = Math.max(
      ...rows.map((row) => (Array.isArray(row) ? row.length : 1)),
    )

    if (width <= 1) {
      const values = rows.map((row) => (Array.isArray(row) ? row[0] : row))
      return {
        columns: [{ key: 'value', label: 'Value' }],
        rows: values.map((value) => ({ value })),
        labels: [],
        values: [],
        singleValue: values[0],
        hasGroup: false,
      }
    }

    const columns = hasGroup
      ? [
          { key: 'group', label: humanize(groupBy) },
          { key: 'value', label: 'Value' },
        ]
      : Array.from({ length: width }, (_, index) => ({
          key: `col_${index}`,
          label: `Column ${index + 1}`,
        }))

    const normalizedRows = rows.map((row) => {
      const cells = Array.isArray(row) ? row : [row]
      const record: Record<string, unknown> = {}
      if (hasGroup) {
        record.group = cells[0]
        record.value = cells[1]
      } else {
        cells.forEach((cell, index) => {
          record[`col_${index}`] = cell
        })
      }
      return record
    })

    const limited = normalizedRows.slice(0, 80)
    return {
      columns,
      rows: normalizedRows,
      labels: limited.map((row) => formatValue(hasGroup ? row.group : row.col_0)),
      values: limited.map((row) => toNumberOrZero(hasGroup ? row.value : row.col_1)),
      singleValue: undefined,
      hasGroup,
    }
  }

  const objectRows = rows as Array<Record<string, unknown>>
  const keys = [...new Set(objectRows.flatMap((row) => Object.keys(row)))]
  const groupKey = hasGroup && keys.includes(groupBy) ? groupBy : keys[0] ?? 'value'
  const valueKey = keys.find((key) => key !== groupKey) ?? groupKey
  const limited = objectRows.slice(0, 80)
  const singleValue =
    objectRows.length === 1 && keys.length === 1 ? objectRows[0]?.[keys[0] ?? 'value'] : undefined

  return {
    columns: keys.map((key) => ({ key, label: humanize(key) })),
    rows: objectRows,
    labels: limited.map((row) => formatValue(row[groupKey])),
    values: limited.map((row) => toNumberOrZero(row[valueKey])),
    singleValue,
    hasGroup: hasGroup && keys.length > 1,
  }
}

function MetricListItem({
  metric,
  active,
  onSelect,
}: {
  metric: MetricSummary
  active: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={cx('metric-item', active && 'metric-item--active')}
      onClick={onSelect}
      aria-pressed={active}
    >
      <span className="metric-item__title">{metric.title || metric.name}</span>
      <code className="metric-item__name">{metric.name}</code>
      {metric.description ? (
        <span className="metric-item__description">{truncate(metric.description, 110)}</span>
      ) : null}
      <span className="metric-item__meta">
        {metric.unit ? <Badge tone="neutral">{metric.unit}</Badge> : null}
        {metric.owner ? <Badge tone="slate">{metric.owner}</Badge> : null}
        {metric.status ? (
          <Badge tone={statusTone(metric.status)} dot>
            {statusLabel(metric.status)}
          </Badge>
        ) : null}
      </span>
    </button>
  )
}

function SemanticView({ source }: { source: SourceSummary }) {
  const toast = useToast()
  const metrics = useAsync((signal) => api.metrics(source.id, signal), [source.id])
  const [approving, setApproving] = useState<string | null>(null)
  const drafts = (metrics.data?.metrics ?? []).filter((m) => m.status === 'draft')

  const approveOne = async (name: string) => {
    setApproving(name)
    try {
      await api.setMetricStatus(name, source.id, 'approved')
      toast.push({ tone: 'success', title: 'Metric approved', message: 'Agents can use it now.' })
      metrics.reload()
    } catch (cause) {
      toast.push({ tone: 'error', title: 'Could not approve', message: describeError(cause).message })
    } finally {
      setApproving(null)
    }
  }

  const approveAll = async () => {
    setApproving('*')
    try {
      const result = await api.approveProposedMetrics(source.id)
      toast.push({ tone: 'success', title: `${result.approved.length} metrics approved` })
      metrics.reload()
    } catch (cause) {
      toast.push({ tone: 'error', title: 'Could not approve', message: describeError(cause).message })
    } finally {
      setApproving(null)
    }
  }

  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [groupBy, setGroupBy] = useState('')
  const [timeFrom, setTimeFrom] = useState('')
  const [timeTo, setTimeTo] = useState('')
  const [result, setResult] = useState<EvaluateMetricResponse | null>(null)
  const [evaluating, setEvaluating] = useState(false)
  const [evaluateError, setEvaluateError] = useState<unknown>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const list = useMemo(() => metrics.data?.metrics ?? [], [metrics.data])
  const selected =
    list.find((metric) => metric.name === selectedName)
    ?? list.find((metric) => metric.name === 'revenue')
    ?? list[0] ?? null
  const health = useAsync(
    (signal) =>
      selected
        ? api.metricHealth(selected.name, source.id, signal)
        : Promise.resolve(undefined),
    [selected?.name, source.id],
    { enabled: Boolean(selected) },
  )

  useEffect(() => {
    const max = health.data?.time_max
    if (!max || timeFrom || timeTo) return
    const latest = new Date(`${String(max).slice(0, 10)}T00:00:00`)
    if (Number.isNaN(latest.getTime())) return
    const start = new Date(latest.getFullYear(), latest.getMonth(), 1)
    const end = new Date(latest.getFullYear(), latest.getMonth() + 1, 1)
    const iso = (value: Date) => value.toISOString().slice(0, 10)
    setTimeFrom(iso(start))
    setTimeTo(iso(end))
  }, [health.data, timeFrom, timeTo])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) return list
    return list.filter(
      (metric) =>
        metric.name.toLowerCase().includes(needle) ||
        (metric.title ?? '').toLowerCase().includes(needle) ||
        (metric.description ?? '').toLowerCase().includes(needle),
    )
  }, [list, search])

  const normalized = useMemo(
    () => normalizeMetricRows(result?.rows ?? [], groupBy),
    [result, groupBy],
  )

  const chartOption = useMemo<ChartOption>(() => {
    if (!normalized || !normalized.hasGroup || normalized.labels.length === 0) return {}
    return {
      animationDuration: 500,
      tooltip: { trigger: 'axis', confine: true, axisPointer: { type: 'shadow' } },
      grid: { left: 68, right: 24, top: 16, bottom: 96 },
      xAxis: {
        type: 'category',
        data: normalized.labels,
        axisLabel: { rotate: 35, color: '#475569', fontSize: 11, interval: 'auto' },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#e2e8f0' } },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#eef2f7' } },
        axisLabel: { color: '#64748b', fontSize: 11 },
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 38,
          data: normalized.values,
          itemStyle: { color: '#2e2e38', borderRadius: [2, 2, 0, 0] },
          emphasis: { itemStyle: { color: '#ffe600', borderColor: '#2e2e38', borderWidth: 1 } },
        },
      ],
    }
  }, [normalized])

  const healthData: MetricHealthResponse | undefined = health.data
  const selectMetric = (metric: MetricSummary) => {
    setSelectedName(metric.name)
    setResult(null)
    setEvaluateError(null)
    setGroupBy('')
  }

  const runEvaluation = async () => {
    if (!selected) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setEvaluating(true)
    setEvaluateError(null)

    const payload: EvaluateMetricRequest = {
      source: source.id,
      compare_previous: true,
      preview_draft: selected.status === 'draft',
    }
    if (groupBy.trim()) payload.group_by = groupBy.trim()
    if (timeFrom) payload.time_from = timeFrom
    if (timeTo) payload.time_to = timeTo

    try {
      const response = await api.evaluateMetric(selected.name, payload, controller.signal)
      setResult(response)
    } catch (cause) {
      if (isAbortError(cause)) return
      setResult(null)
      setEvaluateError(cause)
    } finally {
      setEvaluating(false)
      abortRef.current = null
    }
  }

  const copySql = async () => {
    if (!result?.sql) return
    const copied = await copyText(result.sql)
    toast.push({
      tone: copied ? 'success' : 'error',
      title: copied ? 'SQL copied' : 'Could not copy the SQL',
      message: copied ? 'The generated statement is on your clipboard.' : 'Select the SQL and copy it manually.',
    })
  }

  const rowColumns = useMemo<Array<Column<Record<string, unknown>>>>(
    () =>
      (normalized?.columns ?? []).map((column) => ({
        key: column.key,
        header: column.label,
        render: (row) => formatValue(row[column.key]),
      })),
    [normalized],
  )

  if (metrics.initialLoading) {
    return (
      <LoadingState
        label="Reading metric definitions"
        description="Every metric is compiled from a column that actually exists in the source."
      />
    )
  }

  if (metrics.error) {
    return (
      <ErrorState error={metrics.error} title="Metrics could not be read" onRetry={metrics.reload} />
    )
  }

  if (list.length === 0) {
    return (
      <Card title="What you can measure" bodyPadding="compact">
        <EmptyState
          icon={ChartColumn}
          title="No metrics for this source yet"
          description="Strata proposes metrics from the data when a source is connected or the server restarts. Restart the server to get proposals for a source connected before this feature."
        />
      </Card>
    )
  }

  return (
    <div className="semantic-layout">
      <Card
        title="Metric definitions"
        subtitle={`${list.length} ${list.length === 1 ? 'metric' : 'metrics'}, each compiled to one SQL definition.`}
        bodyPadding="compact"
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={14} aria-hidden="true" />}
            onClick={() => metrics.reload()}
            loading={metrics.loading}
          >
            Refresh
          </Button>
        }
      >
        {drafts.length > 0 ? (
          <Callout tone="warning" title={`${drafts.length} proposed from your data`}>
            Strata read the tables and proposed these metrics. Check a definition, preview it,
            then approve it. Agents only use approved metrics.
            <div className="form-actions">
              <Button size="sm" variant="primary" loading={approving === '*'} onClick={() => void approveAll()}>
                Approve all proposed
              </Button>
            </div>
          </Callout>
        ) : null}
        <TextInput
          label="Filter"
          placeholder="Search by name, title or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          autoComplete="off"
        />
        <div className="metric-list" role="list">
          {filtered.map((metric) => (
            <div role="listitem" key={metric.name}>
              <MetricListItem
                metric={metric}
                active={selected?.name === metric.name}
                onSelect={() => selectMetric(metric)}
              />
            </div>
          ))}
          {filtered.length === 0 ? (
            <p className="muted">No metric matches that filter.</p>
          ) : null}
        </div>
      </Card>

      <div className="panel-stack">
        {selected ? (
          <Card
            title={selected.title || selected.name}
            subtitle={selected.description || 'No description was published with this metric.'}
            actions={
              <div className="chip-row">
                {selected.unit ? <Badge tone="indigo">{selected.unit}</Badge> : null}
                {selected.owner ? <Badge tone="slate">{selected.owner}</Badge> : null}
                <MetricUsageBadge source={source.id} metric={selected.name} />
                {selected.status ? (
                  <Badge tone={statusTone(selected.status)} dot>
                    {statusLabel(selected.status)}
                  </Badge>
                ) : null}
                {selected.status === 'draft' ? (
                  <Button size="sm" variant="primary" loading={approving === selected.name}
                    onClick={() => void approveOne(selected.name)}>
                    Approve
                  </Button>
                ) : null}
              </div>
            }
          >
            <dl className="definition-grid">
              <div>
                <dt>Metric name</dt>
                <dd>
                  <code className="code">{selected.name}</code>
                </dd>
              </div>
              <div>
                <dt>Unit</dt>
                <dd>{selected.unit || '—'}</dd>
              </div>
              <div>
                <dt>Owner</dt>
                <dd>{selected.owner || '—'}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{statusLabel(selected.status)}</dd>
              </div>
            </dl>

            <form
              className="evaluate-form"
              onSubmit={(event) => {
                event.preventDefault()
                void runEvaluation()
              }}
            >
              <div className="form-row">
                <TextInput
                  label="Group by"
                  placeholder="e.g. state, category"
                  value={groupBy}
                  onChange={(event) => setGroupBy(event.target.value)}
                  hint="Optional column to split by"
                  autoComplete="off"
                />
                <TextInput
                  label="From"
                  type="date"
                  value={timeFrom}
                  onChange={(event) => setTimeFrom(event.target.value)}
                />
                <TextInput
                  label="To"
                  type="date"
                  value={timeTo}
                  onChange={(event) => setTimeTo(event.target.value)}
                />
              </div>
              <div className="form-actions">
                <Button
                  type="submit"
                  variant="primary"
                  icon={<Play size={14} aria-hidden="true" />}
                  loading={evaluating}
                >
                  Evaluate metric
                </Button>
                {evaluating ? (
                  <Button
                    variant="ghost"
                    icon={<Square size={13} aria-hidden="true" />}
                    onClick={() => abortRef.current?.abort()}
                  >
                    Cancel
                  </Button>
                ) : null}
                <span className="muted">The number comes from the SQL shown below, not from a cached dashboard.</span>
              </div>
            </form>
          </Card>
        ) : null}

        {selected ? <MetricCharts key={`${selected.name}:${selected.status}`} source={source.id} metric={selected} /> : null}

        {healthData ? (
          <Card
            title="Metric health"
            subtitle="Source rows, time coverage, dimensions and missing dates behind this definition."
            actions={
              <Badge tone={healthData.score >= 90 ? 'teal' : healthData.score >= 70 ? 'amber' : 'rose'} icon={<ShieldCheck size={13} aria-hidden="true" />}>
                {healthData.score}/100
              </Badge>
            }
          >
            <div className="metric-health">
              {healthData.checks.map((check) => (
                <div className={check.passed ? 'metric-check metric-check--pass' : 'metric-check metric-check--fail'} key={check.name}>
                  <span className="metric-check__dot" aria-hidden="true" />
                  <div>
                    <p className="metric-check__name">{check.name}</p>
                    <p className="metric-check__detail">{check.detail}</p>
                  </div>
                </div>
              ))}
            </div>
            {selected?.caveats ? (
              <Callout tone="warning" title="Caveat">
                {selected.caveats}
              </Callout>
            ) : null}
          </Card>
        ) : null}

        {selected ? (
          <SynonymsEditor
            key={`${selected.name}:${(selected.synonyms ?? []).join('|')}`}
            source={source.id}
            metric={selected.name}
            synonyms={selected.synonyms ?? []}
            onSaved={metrics.reload}
          />
        ) : null}

        {selected ? <SqlValidator key={selected.name} source={source.id} metric={selected.name} /> : null}

        {evaluateError ? (
          <Card title="Evaluation failed" bodyPadding="compact">
            <ErrorState error={evaluateError} onRetry={() => void runEvaluation()} compact />
          </Card>
        ) : null}

        {result ? (
          <>
            {normalized && !normalized.hasGroup && normalized.singleValue !== undefined ? (
              <Card title="Result" bodyPadding="compact">
                <div className="metric-result">
                  <span className="metric-result__value">
                    {formatValue(normalized.singleValue)}
                  </span>
                  {selected?.unit ? (
                    <span className="metric-result__unit">{selected.unit}</span>
                  ) : null}
                </div>
                <p className="muted">
                  One governed number. The same definition produces this value in every caller.
                </p>
              </Card>
            ) : null}

            {result && result.prior !== undefined && result.prior !== null ? (
              <Card title="Period comparison" subtitle="Same definition, same filters, the preceding window of equal length.">
                <div className="metric-comparison">
                  <div>
                    <span>Current</span>
                    <strong>{result.formatted?.[0] ?? formatValue(normalized?.singleValue)}</strong>
                    <small>{result.window?.from} → {result.window?.to}</small>
                  </div>
                  <div>
                    <span>Prior</span>
                    <strong>{formatValue(result.prior)}</strong>
                    <small>{result.prior_window?.from} → {result.prior_window?.to}</small>
                  </div>
                  <div>
                    <span>Change</span>
                    <strong className={(result.change ?? 0) < 0 ? 'metric-delta--down' : 'metric-delta--up'}>
                      {result.change_pct !== null && result.change_pct !== undefined
                        ? `${result.change_pct >= 0 ? '+' : ''}${result.change_pct.toFixed(2)}%`
                        : '—'}
                    </strong>
                    <small>{formatValue(result.change)}</small>
                  </div>
                </div>
              </Card>
            ) : null}

            {normalized && normalized.hasGroup && normalized.labels.length > 0 ? (
              <Card
                title="Chart"
                subtitle={`${selected?.title || selected?.name} split by ${groupBy || 'the first returned column'}.`}
              >
                <EChart
                  option={chartOption}
                  height={340}
                  ariaLabel={`Bar chart of ${selected?.title || selected?.name} grouped by ${groupBy}`}
                />
              </Card>
            ) : null}

            <Card
              title="Rows"
              subtitle={`${normalized?.rows.length ?? 0} row${(normalized?.rows.length ?? 0) === 1 ? '' : 's'} returned by the evaluation.`}
              bodyPadding="none"
              actions={
                normalized ? (
                  <Badge tone="neutral">{`${normalized.columns.length} columns`}</Badge>
                ) : null
              }
            >
              <Table
                columns={rowColumns}
                rows={normalized?.rows ?? []}
                rowKey={(_row, index) => String(index)}
                caption={`Result rows for ${selected?.title || selected?.name}`}
                empty="The evaluation returned no rows."
                maxHeight={420}
              />
            </Card>

            <Card
              title="Generated SQL"
              subtitle="Compiled from the definition, so every caller gets the same number."
              actions={
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Copy size={13} aria-hidden="true" />}
                  onClick={() => void copySql()}
                >
                  Copy
                </Button>
              }
            >
              <pre className="code-block" tabIndex={0}>
                <code>{result.sql}</code>
              </pre>
              {result.params && result.params.length > 0 ? (
                <JsonView value={result.params} label="Query parameters" className="json-view--inline" />
              ) : null}
            </Card>
          </>
        ) : null}

        {!result && !evaluateError ? (
          <Card title="Evaluate" bodyPadding="compact">
            <EmptyState
              icon={Table2}
              title="Choose a metric and run it"
              description="Pick a definition on the left, optionally split it by a column or bound it by a date range, then evaluate. The rows, the chart and the SQL all come from the same call."
            />
          </Card>
        ) : null}
      </div>
    </div>
  )
}
