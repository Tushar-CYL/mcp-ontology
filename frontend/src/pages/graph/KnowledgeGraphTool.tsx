import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Network, Plus, SearchX, TriangleAlert, Waypoints } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { KgOverview } from '../../api/types'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { GraphPicture } from './GraphPicture'

/**
 * The Knowledge graph tool: build from the header, then read records as
 * sentences and open the dot picture when you want it.
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

type Phase = 'idle' | 'building' | 'done'

function Builder({ oid, name, choices, onSwitch }: {
  oid: string
  name: string
  choices: Array<{ id: string; name: string }>
  onSwitch: (id: string) => void
}) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [o, setO] = useState<KgOverview | null>(null)
  const [error, setError] = useState<{ message: string; restart: boolean } | null>(null)

  const build = async () => {
    setError(null)
    setPhase('building')
    try {
      const overview = await api.kgOverview(oid)
      setO(overview)
      setPhase('done')
    } catch (e) {
      const msg = describeError(e).message
      setError({ message: msg, restart: /no route|older version/i.test(msg) })
      setPhase('idle')
    }
  }

  useEffect(() => {
    void build()
    // Auto-build once when this ontology opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oid])

  const ready = phase === 'done' && o
  const building = phase === 'building'

  return (
    <div className="page">
      <PageHeader
        eyebrow="Knowledge graph"
        title={name}
        description="Your data, connected. Switch Globes, Record by record, or Connections below."
        actions={(
          <div className="kg-header-actions">
            {choices.length > 1 ? (
              <select className="input" value={oid} aria-label="Choose data" onChange={(e) => onSwitch(e.target.value)}>
                {choices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            ) : null}
            <Button size="sm" variant="primary" icon={<Waypoints size={14} />} loading={building}
              onClick={build}>{ready ? 'Build again' : 'Build knowledge graph'}</Button>
          </div>
        )}
      />

      {error ? (
        <p className="kgb__error"><TriangleAlert size={15} aria-hidden="true" /> {error.restart
          ? <>The server was started before the knowledge graph was added. Stop it (Ctrl+C) and start it again with <code>python run_server.py</code>.</>
          : error.message}</p>
      ) : null}

      {building && !ready ? <LoadingState label="Building knowledge graph" /> : null}
      {ready ? <GraphPicture oid={oid} overview={o} /> : null}
    </div>
  )
}
