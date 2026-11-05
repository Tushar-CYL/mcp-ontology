import { VerdictReceipt } from '../../components/VerdictReceipt'
import { BreakdownChart, TrendChart } from '../../components/MetricCharts'
import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BookOpenCheck,
  FileText,
  GitBranch,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { api } from '../../api/client'
import type { ContextFact, ContextResponse, SourceSummary } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Select, TextArea, TextInput } from '../../components/Field'
import { LoadingState } from '../../components/LoadingState'
import { NoSourceState } from '../../components/NoSourceState'
import { useSource } from '../../context/SourceContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { formatValue, humanize } from '../../utils/format'

type Mode = 'question' | 'entity'


const KIND_LABEL: Record<string, string> = {
  definition: 'Definition',
  lineage: 'Calculation',
  caveat: 'Caveat',
  metric: 'Measured value',
  change: 'Measured change',
  contribution: 'Contribution',
  volume: 'Volume',
  trend: 'Trend',
  relationship: 'Relationship',
  source_row: 'Source row',
  quality: 'Quality',
  review: 'Review',
}

function provenanceTone(provenance?: string): 'teal' | 'amber' | 'neutral' {
  if (provenance === 'measured') return 'teal'
  if (provenance === 'derived') return 'amber'
  return 'neutral'
}

export function ContextPanel() {
  useDocumentTitle('Context')
  const { selectedSource, loading } = useSource()

  if (loading && !selectedSource) return <LoadingState label="Loading sources" />
  if (!selectedSource) return <NoSourceState />
  return <ContextView key={selectedSource.id} source={selectedSource} />
}

function ContextView({ source }: { source: SourceSummary }) {
  const [mode, setMode] = useState<Mode>('question')
  const [question, setQuestion] = useState('')
  // Questions built from THIS dataset's metrics, dimensions, months and
  // entities - never a fixed example from another dataset.
  const suggestions = useAsync((signal) => api.contextSuggestions(source.id, signal), [source.id])
  const suggested = useMemo(() => suggestions.data?.questions ?? [], [suggestions.data])
  useEffect(() => {
    if (!question && suggested.length) setQuestion(suggested[0].text)
  }, [question, suggested])
  const [budget, setBudget] = useState('1800')
  const [selectedClass, setSelectedClass] = useState('')
  const [selectedKey, setSelectedKey] = useState('')
  const [result, setResult] = useState<ContextResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const ontology = useAsync((signal) => api.ontology(source.id, signal), [source.id])
  const classes = ontology.data?.classes ?? []
  const effectiveClass = selectedClass || classes[0]?.name || ''
  // Real keys for the chosen kind, searched on the server (works for a kind
  // with millions of records; a graph sample would miss most of them).
  const [keySearch, setKeySearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(keySearch.trim()), 250)
    return () => clearTimeout(timer)
  }, [keySearch])
  const entityKeys = useAsync(
    (signal) => api.entities(source.id, effectiveClass, debouncedSearch, signal),
    [source.id, effectiveClass, debouncedSearch],
    { enabled: Boolean(effectiveClass) },
  )
  const keys = useMemo(() => entityKeys.data?.keys ?? [], [entityKeys.data])
  const effectiveKey = selectedKey && keys.includes(selectedKey) ? selectedKey : keys[0] ?? ''

  useEffect(() => {
    setResult(null)
    setError(null)
  }, [mode, source.id])

  const build = async () => {
    setError(null)
    if (mode === 'question' && !question.trim()) {
      setError(new Error('Write a question first.'))
      return
    }
    if (mode === 'entity' && (!effectiveClass || !effectiveKey)) {
      setError(new Error('Choose a class and an entity first.'))
      return
    }
    setBusy(true)
    try {
      if (mode === 'question') {
        setResult(await api.context({
          source: source.id,
          question: question.trim(),
          budget_chars: Number(budget) || 1800,
        }))
      } else {
        setResult(await api.context({
          source: source.id,
          class: effectiveClass,
          key: effectiveKey,
          budget_chars: Number(budget) || 1200,
        }))
      }
    } catch (cause) {
      setError(cause)
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  const facts = useMemo(() => result?.facts ?? [], [result])
  const dropped = result?.dropped ?? []
  const groups = useMemo(() => {
    const map = new Map<string, ContextFact[]>()
    for (const fact of facts) {
      const key = fact.kind || 'evidence'
      map.set(key, [...(map.get(key) ?? []), fact])
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [facts])

  return (
    <div className="panel-stack context-workspace">
      <Card
        title="Build evidence, not a summary"
        subtitle="Ask a business question or inspect one entity. The packer selects the highest-value cited facts and drops whole facts that do not fit."
      >
        <div className="context-mode" role="tablist" aria-label="Context mode">
          <button
            type="button"
            role="tab"
            className={mode === 'question' ? 'context-mode__tab context-mode__tab--active' : 'context-mode__tab'}
            aria-selected={mode === 'question'}
            onClick={() => setMode('question')}
          >
            <Search size={14} aria-hidden="true" />
            Ask a question
          </button>
          <button
            type="button"
            role="tab"
            className={mode === 'entity' ? 'context-mode__tab context-mode__tab--active' : 'context-mode__tab'}
            aria-selected={mode === 'entity'}
            onClick={() => setMode('entity')}
          >
            <GitBranch size={14} aria-hidden="true" />
            Inspect an entity
          </button>
          <span className="context-mode__hint">
            {mode === 'question'
              ? 'Question-first context uses the approved metric, period comparison, contributors and source rows.'
              : 'Entity context follows the graph: properties, direct links, cross-source matches and review state.'}
          </span>
        </div>

        {mode === 'question' ? (
          <>
            <TextArea
              label="Business question"
              value={question}
              rows={3}
              onChange={(event) => setQuestion(event.target.value)}
              hint="Name the metric, region, period or comparison you care about. The builder detects what it can and does not guess the rest."
            />
            <div className="form-row">
              <Select
                label="Context budget"
                value={budget}
                options={[
                  { value: '600', label: '600 characters — focused' },
                  { value: '1200', label: '1,200 characters — standard' },
                  { value: '1800', label: '1,800 characters — rich' },
                  { value: '3200', label: '3,200 characters — broad' },
                ]}
                onValueChange={setBudget}
              />
              <div className="context-question-actions">
                <Button
                  variant="primary"
                  icon={<BookOpenCheck size={15} aria-hidden="true" />}
                  loading={busy}
                  onClick={() => void build()}
                >
                  Build context
                </Button>
              </div>
            </div>
            {suggested.length ? (
              <div className="suggestions">
                <p className="field__label">Questions this data can answer</p>
                <div className="example-row">
                  {suggested.map((item) => (
                    <button
                      key={item.text}
                      type="button"
                      className="example-chip"
                      title={`Best answered by the ${item.preset.replace('_', ' ')} agent`}
                      onClick={() => setQuestion(item.text)}
                    >
                      {item.text}
                    </button>
                  ))}
                </div>
                {suggestions.data?.note ? <p className="muted">{suggestions.data.note}</p> : null}
              </div>
            ) : suggestions.loading ? <p className="muted">Reading this dataset for questions…</p> : null}
          </>
        ) : (
          <>
            <div className="form-row">
              <Select
                label="Class"
                value={effectiveClass}
                options={classes.map((item) => ({ value: item.name, label: item.name }))}
                placeholder="Choose a kind of thing"
                onValueChange={(value) => {
                  setSelectedClass(value)
                  setSelectedKey('')
                  setKeySearch('')
                }}
              />
              <TextInput
                label="Find an entity"
                value={keySearch}
                placeholder="Type part of an id"
                hint={entityKeys.data ? `${entityKeys.data.total.toLocaleString()} ${effectiveClass} records` : undefined}
                onChange={(event) => setKeySearch(event.target.value)}
              />
              <Select
                label="Entity"
                value={effectiveKey}
                options={keys.map((key) => ({ value: key, label: key }))}
                placeholder={entityKeys.loading ? 'Loading…' : keys.length === 0 ? 'Nothing matches' : 'Choose an entity'}
                onValueChange={setSelectedKey}
              />
              <Select
                label="Budget"
                value={budget}
                options={[
                  { value: '600', label: '600 characters' },
                  { value: '1200', label: '1,200 characters' },
                  { value: '2400', label: '2,400 characters' },
                ]}
                onValueChange={setBudget}
              />
            </div>
            <div className="form-actions">
              <Button
                variant="primary"
                icon={<BookOpenCheck size={15} aria-hidden="true" />}
                loading={busy}
                onClick={() => void build()}
              >
                Build pack
              </Button>
            </div>
          </>
        )}
        <Callout tone="info">
          The pack is deterministic. A measurement outranks an inference; a fact that does not fit
          is dropped whole, never cut in half. Every fact keeps its citation.
        </Callout>
        {error ? <ErrorState error={error} compact /> : null}
      </Card>

      {busy ? <LoadingState compact label="Selecting evidence" /> : null}
      {!result && !busy ? (
        <EmptyState
          icon={FileText}
          title="No context pack yet"
          description={
            mode === 'question'
              ? 'Ask a question to receive the definition, measured value, comparison, contributors, source records and quality in one cited pack.'
              : 'Choose a class and an entity, then build a pack of properties, links, cross-source matches and review state.'
          }
        />
      ) : null}

      {result ? (
        <>
          {result.focus && typeof result.focus === 'object' && 'type' in result.focus && result.focus.type === 'question' ? (
            <div className="context-question-head">
              <div>
                <span className="page-header__eyebrow">Question context</span>
                <h2>{String(result.focus.question ?? '')}</h2>
                <p>
                  {result.period?.label ? `Period ${result.period.label}` : 'Latest available period'}
                  {result.filters && Object.keys(result.filters).length > 0
                    ? ` · ${Object.entries(result.filters).map(([key, value]) => `${key}=${value}`).join(', ')}`
                    : ''}
                </p>
              </div>
              {result.metric ? (
                <Badge tone="indigo">{result.metric.title || result.metric.name}</Badge>
              ) : null}
            </div>
          ) : null}

          <div className="context-summary">
            <Card title="Readiness" bodyPadding="compact">
              <div className="context-readiness">
                <div className={`context-score context-score--${(result.coverage?.score ?? 0) >= 75 ? 'teal' : (result.coverage?.score ?? 0) >= 45 ? 'amber' : 'rose'}`}>
                  <strong>{Math.round(result.coverage?.score ?? 0)}</strong>
                  <span>/100</span>
                </div>
                <div>
                  <p className="cell-title">
                    {(result.coverage?.score ?? 0) >= 75
                      ? 'Strong evidence coverage'
                      : (result.coverage?.score ?? 0) >= 45
                        ? 'Usable evidence with gaps'
                        : 'Limited evidence'}
                  </p>
                  <p className="muted">
                    {result.facts.length} facts kept · {result.dropped.length} dropped ·{' '}
                    {result.chars} characters
                  </p>
                </div>
              </div>
              {(result.coverage?.missing ?? []).length > 0 ? (
                <div className="context-missing">
                  <span className="evidence__label">Missing from this pack</span>
                  <div className="chip-row">
                    {(result.coverage?.missing ?? []).map((item) => (
                      <Badge key={item} tone="amber">{humanize(item)}</Badge>
                    ))}
                  </div>
                </div>
              ) : (
                <Callout tone="success" title="Complete coverage">
                  The pack contains every evidence group needed for this question.
                </Callout>
              )}
            </Card>
            <Card title="Answer" bodyPadding="compact">
              <VerdictReceipt answerable={result.answerable} receipt={result.receipt} />
              <p className="context-answer">{result.answer}</p>
              {result.charts && (result.charts.trend.length > 0 || result.charts.breakdown.rows.length > 0) ? (
                <div className="metric-charts">
                  {result.charts.trend.length > 0 ? (
                    <div>
                      <p className="chart-title">Trend behind the answer</p>
                      <TrendChart points={result.charts.trend} label="the metric" height={220} />
                    </div>
                  ) : null}
                  {result.charts.breakdown.dimension && result.charts.breakdown.rows.length > 0 ? (
                    <div>
                      <p className="chart-title">What drove it: by {result.charts.breakdown.dimension.toLowerCase()}</p>
                      <BreakdownChart
                        rows={result.charts.breakdown.rows}
                        dimension={result.charts.breakdown.dimension}
                        label="the metric"
                        height={220}
                      />
                    </div>
                  ) : null}
                </div>
              ) : null}
              <div className="chip-row">
                <Badge tone="teal" icon={<ShieldCheck size={12} />}>
                  {result.sources.length} source(s)
                </Badge>
                <Badge tone="neutral">{result.review_pending} review item(s)</Badge>
                <Badge tone="neutral">{result.rendered.length} rendered chars</Badge>
              </div>
            </Card>
          </div>

          <div className="context-fact-groups">
            {groups.map(([kind, groupFacts]) => (
              <Card
                key={kind}
                title={KIND_LABEL[kind] ?? humanize(kind)}
                subtitle={`${groupFacts.length} cited fact${groupFacts.length === 1 ? '' : 's'}`}
                bodyPadding="compact"
              >
                <ul className="context-fact-list">
                  {groupFacts.map((fact, index) => (
                    <li key={`${kind}-${index}`} className="context-fact">
                      <div className="context-fact__head">
                        <Badge tone={provenanceTone(fact.provenance)}>{fact.provenance}</Badge>
                        {fact.citation ? <code>{fact.citation}</code> : null}
                        {fact.confidence !== undefined ? (
                          <span className="muted">{Math.round((fact.confidence ?? 1) * 100)}% confidence</span>
                        ) : null}
                      </div>
                      <p>{fact.text}</p>
                      {fact.as_of ? <small>as of {formatValue(fact.as_of)}</small> : null}
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>

          {dropped.length > 0 ? (
            <Card
              title="Dropped from the pack"
              subtitle="Not hidden: these are the facts the budget left out, with the reason."
              bodyPadding="compact"
            >
              <ul className="context-dropped">
                {dropped.map((fact, index) => (
                  <li key={`dropped-${index}`}>
                    <AlertTriangle size={13} aria-hidden="true" />
                    <span>{fact.text}</span>
                    <Badge tone="slate">{fact.reason || 'budget'}</Badge>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          <Card title="Rendered pack" subtitle="Exactly what an agent or downstream consumer receives.">
            <pre className="code-block">{result.rendered}</pre>
          </Card>
        </>
      ) : null}

      {mode === 'entity' && ontology.error ? <ErrorState error={ontology.error} compact /> : null}
      {mode === 'entity' && entityKeys.error ? <ErrorState error={entityKeys.error} compact /> : null}
    </div>
  )
}
