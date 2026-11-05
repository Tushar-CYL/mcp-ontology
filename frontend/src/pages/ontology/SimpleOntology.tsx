import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, List, Plus } from 'lucide-react'
import { api } from '../../api/client'
import type { OntoListRow, OntoView } from '../../api/types'
import { Button } from '../../components/Button'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { checkedShare, formatCount, sourceLine, timeAgo } from '../../utils/onto'
import { Connect } from './Connect'
import { DeleteOntology } from './DeleteOntology'
import { OntologyView, type Tab } from './OntologyView'

/**
 * The Ontology tool: connect data -> automatic ontology -> use it in Nexus,
 * Excel or any agent. `/tools/ontology/new` connects; `/tools/ontology/:oid`
 * shows one ontology (`?tab=map` / `?tab=use`).
 */
export function SimpleOntology() {
  useDocumentTitle('Ontology')
  const { oid } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const list = useAsync((signal) => api.ontoList(signal), [oid])
  const creating = oid === 'new'
  const listing = oid === 'all'

  useEffect(() => {
    if (oid || !list.data) return
    const latest = [...list.data.ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    navigate(latest ? `/tools/ontology/${encodeURIComponent(latest.id)}` : '/tools/ontology/new',
      { replace: true })
  }, [oid, list.data, navigate])

  if (list.initialLoading && !list.data) return <div className="page"><LoadingState label="Loading" /></div>
  if (list.error) return <div className="page"><ErrorState error={list.error} onRetry={list.reload} /></div>
  if (!oid) return <div className="page"><LoadingState label="Loading" /></div>

  if (listing) {
    const rows = list.data?.ontologies ?? []
    return (
      <div className="page">
        <PageHeader eyebrow="Ontology" title="All ontologies"
          description={`${rows.length} ontolog${rows.length === 1 ? 'y' : 'ies'}. Open one, or delete what you no longer need.`}
          actions={<Button variant="primary" size="sm" icon={<Plus size={14} />}
            onClick={() => navigate('/tools/ontology/new')}>New ontology</Button>} />
        <OntologyTable rows={rows} onOpen={(id) => navigate(`/tools/ontology/${encodeURIComponent(id)}`)}
          onDeleted={list.reload} />
      </div>
    )
  }

  if (creating) {
    return (
      <div className="page">
        <PageHeader eyebrow="Ontology" title="New ontology"
          description="Give it any data, plus any metadata you already have. It finds the business things, explains every field in plain words and proves how they link."
          actions={list.data?.ontologies.length ? (
            <Button variant="ghost" icon={<ArrowLeft size={15} />} onClick={() => navigate(-1)}>Back</Button>) : null} />
        <Connect ai={list.data?.ai} onBuilt={(id) => navigate(`/tools/ontology/${encodeURIComponent(id)}`)} />
      </div>
    )
  }

  const raw = params.get('tab')
  const tab: Tab = raw === 'map' || raw === 'use' ? raw : 'overview'
  return (
    <Workspace key={oid} oid={oid} tab={tab}
      others={list.data?.ontologies.map((o) => ({ id: o.id, name: o.name })) ?? []}
      onTab={(t) => setParams(t === 'overview' ? {} : { tab: t }, { replace: true })}
      onSwitch={(id) => navigate(`/tools/ontology/${encodeURIComponent(id)}`)}
      onNew={() => navigate('/tools/ontology/new')}
      onAll={() => navigate('/tools/ontology/all')}
      onDeleted={() => { list.reload(); navigate('/tools/ontology', { replace: true }) }} />
  )
}

function Workspace({ oid, tab, others, onTab, onSwitch, onNew, onAll, onDeleted }: {
  oid: string
  tab: Tab
  others: Array<{ id: string; name: string }>
  onTab: (tab: Tab) => void
  onSwitch: (id: string) => void
  onNew: () => void
  onAll: () => void
  onDeleted: () => void
}) {
  const [tick, setTick] = useState(0)
  const [fresh, setFresh] = useState<OntoView | null>(null)
  const state = useAsync((signal) => api.ontoView(oid, signal), [oid, tick])
  const view = fresh ?? state.data
  useEffect(() => { setFresh(null) }, [state.data])

  if (!view && state.initialLoading) return <div className="page"><LoadingState label="Loading the ontology" /></div>
  if (!view) return <div className="page"><ErrorState error={state.error} onRetry={state.reload} /></div>
  const updated = timeAgo(view.published_at)
  return (
    <div className="page">
      <PageHeader eyebrow="Ontology" title={view.name}
        description={[view.domain, sourceLine(view.sources, view.metadata), updated && `updated ${updated}`]
          .filter(Boolean).join(' · ')}
        actions={
          <div className="onto-header-actions">
            {others.length > 1 ? (
              <select className="input" value={oid} aria-label="Switch ontology" onChange={(e) => onSwitch(e.target.value)}>
                {others.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            ) : null}
            <Button variant="ghost" size="sm" icon={<List size={14} />} onClick={onAll}>All ontologies</Button>
            <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={onNew}>New ontology</Button>
          </div>
        } />
      <OntologyView view={view} tab={tab} onTab={onTab}
        onChange={(next) => (next ? setFresh(next) : setTick((t) => t + 1))}
        onDeleted={onDeleted} />
    </div>
  )
}

function OntologyTable({ rows, onOpen, onDeleted }: {
  rows: OntoListRow[]
  onOpen: (id: string) => void
  onDeleted: () => void
}) {
  if (!rows.length) {
    return <div className="onto-empty">No ontologies yet. Create one with <strong>New ontology</strong>.</div>
  }
  const sorted = [...rows].sort((a, b) => (b.published_at ?? b.created_at).localeCompare(a.published_at ?? a.created_at))
  return (
    <div className="onto-table">
      <div className="onto-table__head" aria-hidden="true">
        <span>Name</span><span>Built from</span><span>Things</span><span>Confirmed</span><span>Updated</span><span />
      </div>
      {sorted.map((o) => (
        <div key={o.id} className="onto-table__row">
          <button type="button" className="onto-table__name" onClick={() => onOpen(o.id)}>
            <strong>{o.name}</strong>
            {o.domain ? <span>{o.domain}</span> : null}
          </button>
          <span>{sourceLine(o.sources, o.metadata)}</span>
          <span>{formatCount(o.summary.things)} things · {formatCount(o.summary.fields)} fields</span>
          <span>{checkedShare(o.summary)}%</span>
          <span>{timeAgo(o.published_at ?? o.created_at)}</span>
          <span className="onto-table__actions">
            <Button size="sm" variant="secondary" onClick={() => onOpen(o.id)}>Open</Button>
            <DeleteOntology id={o.id} name={o.name} onDeleted={onDeleted} compact />
          </span>
        </div>
      ))}
    </div>
  )
}
