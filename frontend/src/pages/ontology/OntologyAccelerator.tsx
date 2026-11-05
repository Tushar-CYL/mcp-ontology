import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { api, describeError } from '../../api/client'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { cx } from '../../utils/cx'
import { findingInfo, neverAnalysed, sortFindings, STEP_STATUS } from '../../utils/eo'
import { Intake } from './Intake'
import { KnowledgeMap } from './KnowledgeMap'
import { Maturity } from './Maturity'
import { useActingAs } from '../../hooks/useActingAs'
import { PANELS } from './panels'
import { JobLog } from './shared'

type Tab = 'journey' | 'map' | 'maturity'

export function OntologyAccelerator() {
  useDocumentTitle('Ontology Accelerator')
  const { oid } = useParams()
  const navigate = useNavigate()
  const list = useAsync((signal) => api.eoOntologies(signal), [])
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    const first = list.data?.ontologies[0]
    if (!oid && first && !creating) navigate(`/tools/ontology-advanced/${encodeURIComponent(first.id)}`, { replace: true })
  }, [oid, list.data, navigate, creating])

  if (list.initialLoading) return <div className="page"><LoadingState label="Loading ontologies" /></div>
  if (list.error) return <div className="page"><ErrorState error={list.error} onRetry={list.reload} /></div>

  const open = (id: string) => {
    setCreating(false)
    list.reload()
    navigate(`/tools/ontology-advanced/${encodeURIComponent(id)}`)
  }
  if (!oid || creating) {
    return (
      <div className="page">
        <PageHeader eyebrow="Accelerator 1" title="Ontology Accelerator"
          description="Input: your sources and the problem. Output: one governed, versioned enterprise ontology that every tool and agent reads."
          actions={list.data?.ontologies.length ? <Button variant="ghost" onClick={() => setCreating(false)}>Back</Button> : null} />
        <Intake onCreated={open} />
      </div>
    )
  }
  return <Workspace key={oid} oid={oid} ontologies={list.data?.ontologies.map((o) => o.id) ?? []}
    onNew={() => setCreating(true)} onSwitch={open} />
}

function Workspace({ oid, ontologies, onNew, onSwitch }: {
  oid: string
  ontologies: string[]
  onNew: () => void
  onSwitch: (id: string) => void
}) {
  const toast = useToast()
  const [by, setBy] = useActingAs()
  const [tab, setTab] = useState<Tab>('journey')
  const [stepId, setStepId] = useState<string>('concepts')
  const [jobId, setJobId] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const state = useAsync((signal) => api.eoState(oid, signal), [oid, tick])
  const refresh = () => setTick((t) => t + 1)

  const rerun = async () => {
    try {
      setJobId((await api.eoRun(oid)).job_id)
    } catch (error) {
      toast.push({ title: 'Could not start', message: describeError(error).message, tone: 'error' })
    }
  }

  // A new ontology has only its intake. Run the analysis straight away, so
  // nobody is left looking at eleven "waiting" steps.
  const neverRun = Boolean(state.data && neverAnalysed(state.data.steps))
  const autoStarted = useRef(false)
  useEffect(() => {
    if (neverRun && !jobId && !autoStarted.current) {
      autoStarted.current = true
      void rerun()
    }
  })

  if (state.initialLoading) return <div className="page"><LoadingState label="Loading the ontology" /></div>
  if (state.error || !state.data) return <div className="page"><ErrorState error={state.error} onRetry={state.reload} /></div>
  const s = state.data
  const step = s.steps.find((x) => x.id === stepId) ?? s.steps[0]
  const Panel = PANELS[step.id]
  const latest = s.versions[s.versions.length - 1]
  const findings = sortFindings(s.findings.filter((f) => f.status !== 'rejected'))

  return (
    <div className="page">
      <PageHeader eyebrow="Accelerator 1 · Ontology" title={s.ontology.name}
        description={s.ontology.problem}
        meta={<span className="chip-row">
          <Badge tone="indigo">Maturity level {s.maturity.level}</Badge>
          <Badge tone={latest ? 'teal' : 'slate'}>{latest ? `Published v${latest.version}` : 'Not published'}</Badge>
          <Badge tone="neutral">{s.ontology.sources.length} sources</Badge>
        </span>}
        actions={<div className="eo-header-actions">
          <label className="eo-acting">Acting as
            <input className="input" value={by} onChange={(e) => setBy(e.target.value || 'steward')} aria-label="Acting as" />
          </label>
          {ontologies.length > 1 ? (
            <select className="input" value={oid} onChange={(e) => onSwitch(e.target.value)} aria-label="Ontology">
              {ontologies.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
          ) : null}
          <Button variant="secondary" icon={<RefreshCw size={15} />} onClick={rerun} disabled={Boolean(jobId)}>Re-run</Button>
          <Button variant="ghost" onClick={onNew}>New</Button>
        </div>} />

      {jobId ? (
        <Card title="Analysing your sources" subtitle="Profiling, concepts, meanings, links, identity, freshness and rules. This usually takes seconds; very large sources take longer.">
          <JobLog jobId={jobId} onFinished={(job) => {
            setJobId(null)
            refresh()
            toast.push({ title: job.status === 'done' ? 'Accelerator finished' : 'Accelerator failed',
              message: job.error ?? undefined, tone: job.status === 'done' ? 'success' : 'error' })
          }} />
        </Card>
      ) : null}

      {findings.length ? (
        <div className="eo-findings" aria-label="What the accelerator found">
          {findings.slice(0, 4).map((f) => (
            <div key={f.key} className={`eo-finding eo-finding--${findingInfo(f.type).tone}`}>
              <p className="eo-finding__title">{findingInfo(f.type).title}</p>
              <p className="eo-finding__detail">{f.detail}</p>
            </div>
          ))}
          {findings.length > 4 ? <p className="muted">+{findings.length - 4} more findings in the steps below</p> : null}
        </div>
      ) : null}

      <div className="eo-tabs" role="tablist">
        {(['journey', 'map', 'maturity'] as Tab[]).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t}
            className={cx('eo-tab', tab === t && 'is-active')} onClick={() => setTab(t)}>
            {t === 'journey' ? 'Journey' : t === 'map' ? 'Knowledge map' : `Maturity (level ${s.maturity.level})`}
          </button>
        ))}
      </div>

      {tab === 'journey' ? (
        <div className="eo-journey">
          <nav className="eo-stepper" aria-label="Journey steps">
            <ol>
              {s.steps.map((x, i) => (
                <li key={x.id}>
                  <button type="button" className={cx('eo-step', x.id === step.id && 'is-active', `is-${x.status}`)}
                    onClick={() => setStepId(x.id)} aria-current={x.id === step.id ? 'step' : undefined}>
                    <span className="eo-step__num">{i + 1}</span>
                    <span className="eo-step__text">
                      <span className="eo-step__title">{x.title}</span>
                      <span className="eo-step__meta">
                        <Badge tone={STEP_STATUS[x.status].tone}>{STEP_STATUS[x.status].label}</Badge>
                        {x.pending ? <span className="muted">{x.pending} to review</span> : null}
                        <span className="muted">L{x.level}</span>
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </nav>
          <section className="eo-step-panel">
            <Callout tone="info" title={step.title}>{step.what}</Callout>
            <Panel oid={oid} state={s} by={by} onChanged={refresh} />
          </section>
        </div>
      ) : tab === 'map' ? (
        <KnowledgeMap oid={oid} version={tick} />
      ) : (
        <Maturity card={s.maturity} />
      )}
    </div>
  )
}
