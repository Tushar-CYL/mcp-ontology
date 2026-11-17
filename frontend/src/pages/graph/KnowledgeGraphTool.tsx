import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CircleCheck, Network, Plus, SearchX, TriangleAlert, Waypoints } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { KgOverview } from '../../api/types'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { UseElsewhere } from '../../components/UseElsewhere'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { cx } from '../../utils/cx'
import { formatCount } from '../../utils/onto'
import { GraphPicture } from './GraphPicture'

/**
 * The Knowledge graph tool, kept simple: pick the data, press Build, watch
 * the three steps (read the schema, read the data, make the graph), then
 * see the graph of real records and click through it.
 */
export function KnowledgeGraphTool() {
  useDocumentTitle('Knowledge graph')
  const { oid } = useParams()
  const navigate = useNavigate()
  const list = useAsync((signal) => api.ontoList(signal), [])
  const ontologies = useMemo(() => list.data?.ontologies ?? [], [list.data])

  useEffect(() => {
    if (oid || !ontologies.length) return
    const latest = [...ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    navigate(`/tools/graph/${encodeURIComponent(latest.id)}`, { replace: true })
  }, [oid, ontologies, navigate])

  if (list.initialLoading && !list.data) return <div className="page"><LoadingState label="Loading" /></div>
  if (list.error) return <div className="page"><ErrorState error={list.error} onRetry={list.reload} /></div>
  if (!ontologies.length) {
    return (
      <div className="page">
        <PageHeader eyebrow="Knowledge graph" title="Knowledge graph" />
        <EmptyState icon={Network} title="Connect your data first"
          description="A knowledge graph is your data connected: every record becomes a point, every link between records a line. Connect your data on the Ontology page; it appears here."
          action={<Button variant="primary" icon={<Plus size={15} />}
            onClick={() => navigate('/tools/ontology/new')}>Connect data</Button>} />
      </div>
    )
  }
  if (!oid) return <div className="page"><LoadingState label="Opening" /></div>
  const current = ontologies.find((o) => o.id === oid)
  if (!current) {
    return (
      <div className="page">
        <PageHeader eyebrow="Knowledge graph" title="Knowledge graph" />
        <EmptyState icon={SearchX} title="This data is no longer here"
          description={<>There is nothing called <code>{oid}</code>. It may have been deleted.</>}
          action={<Button variant="primary" onClick={() => navigate('/tools/graph', { replace: true })}>Open the latest</Button>} />
      </div>
    )
  }
  return (
    <Builder key={oid} oid={oid} name={current.name}
      choices={ontologies.map((o) => ({ id: o.id, name: o.name }))}
      onSwitch={(id) => navigate(`/tools/graph/${encodeURIComponent(id)}`)} />
  )
}

type Phase = 'idle' | 'schema' | 'data' | 'graph' | 'done'
const ORDER: Phase[] = ['idle', 'schema', 'data', 'graph', 'done']
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

function Builder({ oid, name, choices, onSwitch }: {
  oid: string
  name: string
  choices: Array<{ id: string; name: string }>
  onSwitch: (id: string) => void
}) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [o, setO] = useState<KgOverview | null>(null)
  const [error, setError] = useState<{ message: string; restart: boolean } | null>(null)
  const reached = (p: Phase) => ORDER.indexOf(phase) >= ORDER.indexOf(p)

  const build = async () => {
    setError(null)
    setPhase('schema')
    try {
      const [overview] = await Promise.all([api.kgOverview(oid), wait(500)])
      setO(overview)
      setPhase('data')
      await wait(600)
      setPhase('graph')
      await wait(600)
      setPhase('done')
    } catch (e) {
      const msg = describeError(e).message
      setError({ message: msg, restart: /no route|older version/i.test(msg) })
      setPhase('idle')
    }
  }

  const tables = o?.schema.filter((t) => !t.graph) ?? []
  const graphs = o?.schema.filter((t) => t.graph) ?? []
  const columns = tables.reduce((n, t) => n + t.columns.length, 0)
  const problems = o?.health.filter((h) => h.severity === 'warning') ?? []

  return (
    <div className="page">
      <PageHeader eyebrow="Knowledge graph" title={name}
        description="Your data, connected: every record becomes a point and every link between records a line."
        actions={choices.length > 1 ? (
          <select className="input" value={oid} aria-label="Choose data" onChange={(e) => onSwitch(e.target.value)}>
            {choices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        ) : null} />

      <section className="kgb" aria-label="How the knowledge graph is built">
        <div className="kgb__head">
          <div>
            <h2>How the knowledge graph is built</h2>
            <p className="kg-muted">Three steps, straight from your data. Nothing is copied or changed.</p>
          </div>
          <Button variant="primary" icon={<Waypoints size={15} />} loading={phase !== 'idle' && phase !== 'done'}
            onClick={build}>{phase === 'done' ? 'Build again' : 'Build knowledge graph'}</Button>
        </div>

        {error ? (
          <p className="kgb__error"><TriangleAlert size={15} aria-hidden="true" /> {error.restart
            ? <>The server was started before the knowledge graph was added. Stop it (Ctrl+C) and start it again with <code>python run_server.py</code>.</>
            : error.message}</p>
        ) : null}

        <ol className="kgb__steps">
          <Step n={1} title="Read the schema" active={phase === 'schema'} done={reached('data')}
            summary={o ? `${formatCount(tables.length)} tables, ${formatCount(columns)} columns${graphs.length ? `, ${graphs.length} graph file${graphs.length > 1 ? 's' : ''}` : ''}` : 'Which tables there are, their columns and their keys'}>
            {reached('data') && o ? (
              <ul className="kgb__list">
                {tables.map((t) => (
                  <li key={t.table}>
                    <strong>{t.thing}</strong>
                    <span>{t.table.split('.').slice(1).join('.')} · {t.columns.length} columns{t.key ? ` · key ${t.key.join(' + ')}` : ''}</span>
                  </li>
                ))}
                {graphs.map((t) => <li key={t.table}><strong>{t.table}</strong><span>entities and relations</span></li>)}
              </ul>
            ) : null}
          </Step>

          <Step n={2} title="Read the data" active={phase === 'data'} done={reached('graph')}
            summary={o && reached('graph') ? `${formatCount(o.summary.entities)} records` : 'How many records each table holds'}>
            {reached('graph') && o ? (
              <ul className="kgb__list">
                {o.things.map((t) => (
                  <li key={t.thing}><strong>{t.thing}</strong><span>{formatCount(t.entities)} records</span></li>
                ))}
                {o.graphs.map((g) => (
                  <li key={g.source}><strong>{g.source}</strong><span>{formatCount(g.entities)} entities</span></li>
                ))}
              </ul>
            ) : null}
          </Step>

          <Step n={3} title="Make the knowledge graph" active={phase === 'graph'} done={reached('done')}
            summary={o && reached('done')
              ? `${formatCount(o.summary.entities)} points, ${formatCount(o.summary.connections)} lines`
              : 'Each record becomes a point; each link a line'}>
            {reached('done') && o ? (
              <ul className="kgb__list">
                {o.connections.map((c) => (
                  <li key={c.key}>
                    <strong>{c.from_thing} → {c.to_thing}</strong>
                    <span>{formatCount(c.connections)} lines{c.orphans ? ` · ${formatCount(c.orphans)} point at nothing` : ''}</span>
                  </li>
                ))}
                {o.graphs.map((g) => (
                  <li key={g.source}><strong>{g.source}</strong><span>{formatCount(g.connections)} lines</span></li>
                ))}
              </ul>
            ) : null}
          </Step>
        </ol>

        {phase === 'done' && o ? (
          <p className={cx('kgb__verdict', problems.length ? 'is-warn' : 'is-ok')}>
            {problems.length
              ? <><TriangleAlert size={15} aria-hidden="true" /> Built. {problems.map((h) => h.text).join('. ')}.</>
              : <><CircleCheck size={15} aria-hidden="true" /> Built. Every line joins two records that exist.</>}
          </p>
        ) : null}
      </section>

      {phase === 'done' ? <GraphPicture oid={oid} /> : null}

      <UseElsewhere layer="graph" oid={oid} />
    </div>
  )
}

function Step({ n, title, summary, active, done, children }: {
  n: number
  title: string
  summary: string
  active: boolean
  done: boolean
  children?: React.ReactNode
}) {
  return (
    <li className={cx('kgb__step', active && 'is-active', done && 'is-done')}>
      <div className="kgb__step-head">
        <span className="kgb__num" aria-hidden="true">{done ? <CircleCheck size={16} /> : n}</span>
        <div>
          <h3>{title}</h3>
          <p>{active ? 'Working...' : summary}</p>
        </div>
      </div>
      {children}
    </li>
  )
}
