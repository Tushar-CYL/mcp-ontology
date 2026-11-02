import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Database,
  FileCheck2,
  Layers,
  Network,
  ShieldCheck,
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

const LAYER_CARDS = [
  {
    key: 'ontology',
    index: '1',
    title: 'Ontology',
    question: 'What exists, and what does it mean?',
    icon: Layers,
  },
  {
    key: 'graph',
    index: '2',
    title: 'Knowledge graph',
    question: 'How are the entities connected?',
    icon: Network,
  },
  {
    key: 'semantic',
    index: '3',
    title: 'Semantic layer',
    question: 'What does each metric mean?',
    icon: FileCheck2,
  },
  {
    key: 'context',
    index: '4',
    title: 'Context',
    question: 'Which evidence answers the question?',
    icon: ShieldCheck,
  },
] as const

export function Onboarding() {
  useDocumentTitle('Onboarding')
  const { sources, loading, error, refresh, selectSource, selectedSource } = useSource()
  const toast = useToast()
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<unknown>(null)
  const [elapsed, setElapsed] = useState(0)
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
    try {
      const created = await api.createSource({
        path: trimmed,
        name: name.trim() || undefined,
      })
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
        description="Connect one source. The middle layer derives the ontology, builds the graph, defines the metrics and packs cited evidence for an agent. Nothing is invented along the way."
        actions={
          selectedSource ? (
            <Link to="/layers" className="btn btn--primary btn--md">
              Continue to layers
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          ) : null
        }
      />

      {loading && sources.length === 0 ? <LoadingState label="Loading sources" /> : null}
      {error ? <ErrorState error={error} onRetry={() => void refresh()} /> : null}

      <div className="grid-2 grid-2--wide-left">
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
              Reading and profiling the source, then building nodes and edges. Large sources can take
              minutes. Elapsed: <strong>{formatDuration(elapsed)}</strong>. This page stays open; do not
              start a second build.
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

        <Card
          title="What this platform gives you"
          subtitle="Four explainable layers under one governed model."
          className="panel-stack"
        >
          <div className="definition-grid">
            {LAYER_CARDS.map((layer) => {
              const Icon = layer.icon
              return (
                <div className="definition-card" key={layer.key}>
                  <span className="definition-card__index">{layer.index}</span>
                  <Icon size={18} aria-hidden="true" />
                  <div>
                    <p className="definition-card__title">{layer.title}</p>
                    <p className="definition-card__question">{layer.question}</p>
                  </div>
                </div>
              )
            })}
          </div>
          <Callout tone="success" title="The promise">
            Connect data once. Define meaning once. Reuse it everywhere — BI first, AI-ready by
            design.
          </Callout>
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
