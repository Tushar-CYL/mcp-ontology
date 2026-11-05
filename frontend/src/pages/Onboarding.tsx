import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { LAYER_FLOW } from '../utils/governance'
import {
  ArrowRight,
  Database,
  Layers,
  Network,
  Sparkles,
  Upload,
} from 'lucide-react'
import { api } from '../api/client'
import { useSource } from '../context/SourceContext'
import { useToast } from '../context/ToastContext'
import { formatDuration, formatNumber } from '../utils/format'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Callout } from '../components/Callout'
import { Card } from '../components/Card'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Stat } from '../components/Stat'
import { TextInput } from '../components/Field'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

export function Onboarding() {
  useDocumentTitle('Onboarding')
  const { sources, loading, error, refresh, selectSource, selectedSource } = useSource()
  const toast = useToast()
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<unknown>(null)
  const [elapsed, setElapsed] = useState(0)
  const [steps, setSteps] = useState<Array<{ t: number; text: string }>>([])
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (!busy) {
      if (timer.current !== null) window.clearInterval(timer.current)
      timer.current = null
      return
    }
    setElapsed(0)
    const started = Date.now()
    timer.current = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000))
    }, 1000)
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current)
      timer.current = null
    }
  }, [busy])

  const connect = async () => {
    const trimmed = path.trim()
    if (!trimmed) {
      setFormError(new Error('Enter a file, folder or database URL first.'))
      return
    }
    setBusy(true)
    setFormError(null)
    setSteps([])
    try {
      // Load in the background and poll: a big source never ties up one
      // request for minutes, and the rest of the app keeps answering.
      const { job_id: jobId } = await api.startSourceLoad({
        path: trimmed,
        name: name.trim() || undefined,
      })
      let job = await api.job(jobId)
      while (job.status === 'running') {
        setSteps(job.steps)
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
        job = await api.job(jobId)
      }
      setSteps(job.steps)
      if (job.status === 'failed' || !job.result) {
        throw new Error(job.error ?? 'The load failed.')
      }
      const created = job.result
      await refresh()
      selectSource(created.id)
      toast.push({
        tone: 'success',
        title: 'Source connected',
        message: `${created.name} is built: ${formatNumber(created.classes)} kinds of thing, ${formatNumber(
          created.nodes,
        )} nodes.`,
      })
    } catch (cause) {
      setFormError(cause)
    } finally {
      setBusy(false)
    }
  }

  const layerStats = useMemo(() => {
    if (!selectedSource) return null
    return {
      classes: selectedSource.classes,
      relations: selectedSource.relations,
      nodes: selectedSource.nodes,
      edges: selectedSource.edges,
    }
  }, [selectedSource])

  return (
    <div className="page">
      <PageHeader
        eyebrow="Start here"
        title="Make every data source usable for trusted decisions"
        description="Connect one source. Strata turns it into four layers (a catalogue, a connected map, a rulebook of approved numbers and a cited briefing folder) and gives you agents that use all four and say when they cannot answer."
      />

      {selectedSource ? (
        <nav className="flow-strip" aria-label="How Strata works">
          {LAYER_FLOW.map((step, index) => {
            const count =
              step.layer === 'ontology' ? `${selectedSource.classes} kinds of thing`
                : step.layer === 'graph' ? `${selectedSource.nodes.toLocaleString()} records`
                  : step.layer === 'semantic' ? 'approved metrics'
                    : step.layer === 'context' ? 'cited evidence'
                      : index === 0 ? (selectedSource.name || selectedSource.id)
                        : '6 agent types'
            return (
              <Link key={step.to} to={step.to} className="flow-step">
                <span className="flow-step__label">{step.label}</span>
                <span className="flow-step__count">{count}</span>
                {index < LAYER_FLOW.length - 1 ? (
                  <ArrowRight size={14} aria-hidden="true" className="flow-step__arrow" />
                ) : null}
              </Link>
            )
          })}
        </nav>
      ) : null}

      {loading && sources.length === 0 ? <LoadingState label="Loading sources" /> : null}
      {error ? <ErrorState error={error} onRetry={() => void refresh()} /> : null}

      <div className="onboarding-main">
        <Card
          title="Connect a data source"
          subtitle="A database file, a folder of CSV/Parquet/JSON/Excel, a single file, an RDF graph or a database URL."
        >
          <div className="form-row">
            <TextInput
              label="Source path or URL"
              placeholder="data/raw/revenue_huge"
              value={path}
              onChange={(event) => setPath(event.target.value)}
              disabled={busy}
              hint="The API reads the source once, derives the four layers and records build warnings."
              required
            />
            <TextInput
              label="Source name (optional)"
              placeholder="revenue"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={busy}
              hint="Used as the source id; defaults to the folder or file name."
            />
          </div>
          {busy ? (
            <Callout tone="info" title="Building the four layers">
              Elapsed: <strong>{formatDuration(elapsed)}</strong>. The rest of Strata keeps working while
              this runs.
              {steps.length ? (
                <ol className="load-steps">
                  {steps.slice(-8).map((step) => (
                    <li key={`${step.t}-${step.text}`}>
                      <span className="muted">{step.t.toFixed(0)}s</span> {step.text}
                    </li>
                  ))}
                </ol>
              ) : null}
            </Callout>
          ) : null}
          {formError ? <ErrorState error={formError} compact /> : null}
          <div className="form-actions">
            <Button
              variant="primary"
              icon={<Upload size={15} aria-hidden="true" />}
              loading={busy}
              onClick={() => void connect()}
            >
              Connect source
            </Button>
            <span className="muted">
              No code per dataset. A bad file is skipped with a warning instead of failing the source.
            </span>
          </div>
        </Card>

      </div>

      {sources.length > 0 ? (
        <Card
          title="Connected sources"
          subtitle="Each source keeps its own classes, graph, metrics and evidence. Select one to explore."
        >
          <div className="source-grid">
            {sources.map((source) => {
              const active = source.id === selectedSource?.id
              return (
                <button
                  key={source.id}
                  type="button"
                  className={active ? 'source-card source-card--active' : 'source-card'}
                  onClick={() => selectSource(source.id)}
                  aria-pressed={active}
                >
                  <div className="source-card__head">
                    <span className="source-card__icon" aria-hidden="true">
                      <Database size={17} />
                    </span>
                    <div>
                      <p className="source-card__name">{source.name || source.id}</p>
                      <p className="source-card__origin">{source.origin}</p>
                    </div>
                    <Badge tone={source.status === 'built' ? 'teal' : 'amber'}>{source.status}</Badge>
                  </div>
                  <div className="source-card__stats">
                    <span>{formatNumber(source.classes)} classes</span>
                    <span>{formatNumber(source.relations)} relations</span>
                    <span>{formatNumber(source.nodes)} nodes</span>
                    <span>{formatNumber(source.edges)} edges</span>
                  </div>
                  {source.warnings.length > 0 ? (
                    <p className="source-card__warning">
                      {source.warnings.length} warning{source.warnings.length === 1 ? '' : 's'}:{' '}
                      {source.warnings[0]}
                    </p>
                  ) : (
                    <p className="source-card__ok">No reader warnings</p>
                  )}
                </button>
              )
            })}
          </div>
          {selectedSource && layerStats ? (
            <div className="stat-grid stat-grid--3">
              <Stat label="Kinds of thing" value={formatNumber(layerStats.classes)} icon={Layers} />
              <Stat label="Relations" value={formatNumber(layerStats.relations)} icon={Network} />
              <Stat label="Graph" value={formatNumber(layerStats.nodes)} hint={`${formatNumber(layerStats.edges)} links`} icon={Sparkles} />
            </div>
          ) : null}
        </Card>
      ) : null}
    </div>
  )
}
