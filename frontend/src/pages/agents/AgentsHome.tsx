import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bot, Copy, Lock, Plus } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { OntoAgent } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { cx } from '../../utils/cx'
import { AgentForm } from './AgentForm'
import { AgentPanel } from './AgentPanel'
import { KIND_ICON } from './kinds'

/**
 * Agents: the built-ins Strata works out from your data (ready to use, nothing
 * to set up), and your own - a copy of a built-in, or one made from scratch.
 */
export function AgentsHome() {
  useDocumentTitle('Agents')
  const { oid } = useParams()
  const navigate = useNavigate()
  const list = useAsync((signal) => api.ontoList(signal), [])
  const ontologies = useMemo(() => list.data?.ontologies ?? [], [list.data])
  useEffect(() => {
    if (oid || !ontologies.length) return
    const latest = [...ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    navigate(`/agents/${encodeURIComponent(latest.id)}`, { replace: true })
  }, [oid, ontologies, navigate])

  if (list.initialLoading && !list.data) return <div className="page"><LoadingState label="Loading" /></div>
  if (list.error) return <div className="page"><ErrorState error={list.error} onRetry={list.reload} /></div>
  if (!ontologies.length) {
    return (
      <div className="page">
        <PageHeader eyebrow="Agents" title="Agents" />
        <EmptyState icon={Bot} title="Connect your data first"
          description="Agents are worked out from your ontology: build or import one first."
          action={<Button variant="primary" icon={<Plus size={15} />} onClick={() => navigate('/tools/ontology/new')}>New ontology</Button>} />
      </div>
    )
  }
  if (!oid) return <div className="page"><LoadingState label="Opening" /></div>
  const current = ontologies.find((o) => o.id === oid)
  return (
    <Workspace key={oid} oid={oid} name={current?.name ?? oid}
      choices={ontologies.map((o) => ({ id: o.id, name: o.name }))}
      onSwitch={(id) => navigate(`/agents/${encodeURIComponent(id)}`)} />
  )
}

type Mode = { open: string } | { form: 'new' } | { form: 'edit'; id: string } | null

function Workspace({ oid, name, choices, onSwitch }: {
  oid: string
  name: string
  choices: Array<{ id: string; name: string }>
  onSwitch: (id: string) => void
}) {
  const toast = useToast()
  const [tick, setTick] = useState(0)
  const state = useAsync((signal) => api.ontoAgents(oid, signal), [oid, tick])
  const older = useAsync((signal) => api.agents(signal), [])
  const [mode, setMode] = useState<Mode>(null)
  // The agent just made by "copy": known before the list reloads, so its
  // form opens filled in, not blank.
  const [justMade, setJustMade] = useState<OntoAgent | null>(null)
  const reload = () => setTick((t) => t + 1)

  if (state.initialLoading && !state.data) return <div className="page"><LoadingState label="Working out the agents for your data" /></div>
  if (!state.data) {
    const msg = describeError(state.error).message
    return (
      <div className="page">
        <PageHeader eyebrow="Agents" title={name} />
        {/no route|older version/i.test(msg)
          ? <EmptyState icon={Bot} title="Restart the server" description="The server is older than this page. Stop it (Ctrl+C) and start it again with python run_server.py." />
          : <ErrorState error={state.error} onRetry={state.reload} />}
      </div>
    )
  }
  const data = state.data
  const all = [...data.builtin, ...data.mine]
  const opened = mode && 'open' in mode ? all.find((a) => a.id === mode.open) ?? null : null
  const editing = mode && 'form' in mode && mode.form === 'edit'
    ? data.mine.find((a) => a.id === mode.id) ?? (justMade?.id === mode.id ? justMade : null) : null
  const formReady = mode && 'form' in mode && (mode.form === 'new' || editing)

  const copy = async (a: OntoAgent) => {
    try {
      const made = await api.copyOntoAgent(a.id)
      setJustMade(made)
      toast.push({ tone: 'success', title: 'Copy made', message: `${made.name}: change it as you like. The original stays as it is.` })
      reload()
      setMode({ form: 'edit', id: made.id })
    } catch (e) {
      toast.push({ tone: 'error', title: 'Could not copy', message: describeError(e).message })
    }
  }

  return (
    <div className="page">
      <PageHeader eyebrow="Agents" title={name}
        description="Ready-made agents for this data: ask them here, or connect them to Claude, Cursor or your own code. Want one that works differently? Copy one, or create your own."
        actions={
          <div className="page-header__actions">
            {choices.length > 1 ? (
              <select className="input" value={oid} aria-label="Choose data" onChange={(e) => onSwitch(e.target.value)}>
                {choices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            ) : null}
            <Button variant="primary" icon={<Plus size={15} />} onClick={() => setMode({ form: 'new' })}>Create agent</Button>
          </div>
        } />

      <div className={cx('ag-layout', (opened || (mode && 'form' in mode)) && 'has-side')}>
        <div className="ag-main">
          <h2 className="sem-h">Built-in agents <small>{data.builtin.length} from your data, ready to use</small></h2>
          <section className="ag-grid">
            {data.builtin.map((a) => (
              <AgentCard key={a.id} a={a} active={opened?.id === a.id}
                onOpen={() => setMode({ open: a.id })} onCopy={() => void copy(a)} />
            ))}
          </section>

          <h2 className="sem-h">Your agents <small>{data.mine.length ? `${data.mine.length}` : 'none yet'}</small></h2>
          {data.mine.length ? (
            <section className="ag-grid">
              {data.mine.map((a) => (
                <AgentCard key={a.id} a={a} active={opened?.id === a.id} base={all.find((b) => b.id === a.base)?.name}
                  onOpen={() => setMode({ open: a.id })} onCopy={() => void copy(a)} />
              ))}
            </section>
          ) : (
            <p className="muted ag-none">Copy a built-in agent to change how it works, or <button type="button" className="sem-link"
              onClick={() => setMode({ form: 'new' })}>create one from scratch</button>.</p>
          )}
          {older.data?.agents.length ? (
            <p className="muted ag-none">
              You also have {older.data.agents.length} older agent(s) set up per data source: <Link to="/agents/older">open them</Link>.
            </p>
          ) : null}
        </div>

        {opened ? (
          <AgentPanel key={opened.id} agent={opened} onClose={() => setMode(null)} onCopy={() => void copy(opened)}
            onEdit={() => setMode({ form: 'edit', id: opened.id })}
            onDeleted={() => { setMode(null); reload() }} />
        ) : null}
        {formReady && mode && 'form' in mode ? (
          <AgentForm key={mode.form === 'edit' ? mode.id : 'new'} oid={oid} list={data} editing={editing}
            onCancel={() => setMode(null)}
            onSaved={(a) => { reload(); setMode({ open: a.id }) }} />
        ) : null}
      </div>
    </div>
  )
}

function AgentCard({ a, active, base, onOpen, onCopy }: {
  a: OntoAgent
  active: boolean
  base?: string
  onOpen: () => void
  onCopy: () => void
}) {
  const Icon = KIND_ICON[a.kind]
  return (
    <article className={cx('ag-card', active && 'is-active')}>
      <button type="button" className="ag-card__open" onClick={onOpen} aria-label={`Open ${a.name}`}>
        <span className="ag-card__icon"><Icon size={18} aria-hidden="true" /></span>
        <span className="ag-card__name">{a.name}</span>
        {a.builtin ? <Lock size={12} className="ag-card__lock" aria-label="Built-in: copy it to change it" /> : null}
      </button>
      <p className="ag-card__job">{a.job}</p>
      {a.why ? <p className="ag-card__why">{a.why}</p> : null}
      {base ? <p className="ag-card__why">Copied from {base}</p> : null}
      <ul className="ag-card__ex">
        {a.examples.slice(0, 3).map((e) => <li key={e.text}>“{e.text}”</li>)}
      </ul>
      <div className="ag-card__foot">
        <span className="ag-card__layers">{a.layers.map((l) => <Badge key={l} tone="neutral">{l}</Badge>)}</span>
        <span className="ag-card__btns">
          <Button size="sm" variant="primary" onClick={onOpen}>Ask</Button>
          <Button size="sm" variant="ghost" icon={<Copy size={13} />} onClick={onCopy}
            title={a.builtin ? 'Make a copy you can change' : 'Duplicate'}>{a.builtin ? 'Copy' : 'Duplicate'}</Button>
        </span>
      </div>
    </article>
  )
}
