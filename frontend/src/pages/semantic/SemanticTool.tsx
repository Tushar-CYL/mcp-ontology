import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BadgeCheck, ChevronDown, CircleHelp, Plus, Scale, SearchX, Sparkles, TriangleAlert, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { SemCard, SemDecision } from '../../api/types'
import { Button } from '../../components/Button'
import { EChart } from '../../components/EChart'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { ProofMark } from '../../components/ProofMark'
import { SuggestionChips } from '../../components/SuggestionChips'
import { TrustPanel } from '../../components/TrustPanel'
import { UseElsewhere } from '../../components/UseElsewhere'
import { WhatDepends } from '../../components/WhatDepends'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useSuggestions } from '../../hooks/useSuggestions'
import { cx } from '../../utils/cx'
import { chartOption, compact, sparkOption } from '../context/charts'

/**
 * The Semantic tool: one governed number per business word. Pictures first:
 * the decisions people must take, then every metric as a card with its value
 * and trend. A card opens its breakdown and its receipt.
 */
export function SemanticTool() {
  useDocumentTitle('Semantic')
  const { oid } = useParams()
  const navigate = useNavigate()
  const list = useAsync((signal) => api.ontoList(signal), [])
  const ontologies = useMemo(() => list.data?.ontologies ?? [], [list.data])

  useEffect(() => {
    if (oid || !ontologies.length) return
    const latest = [...ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    navigate(`/tools/semantic/${encodeURIComponent(latest.id)}`, { replace: true })
  }, [oid, ontologies, navigate])

  if (list.initialLoading && !list.data) return <div className="page"><LoadingState label="Loading" /></div>
  if (list.error) return <div className="page"><ErrorState error={list.error} onRetry={list.reload} /></div>
  if (!ontologies.length) {
    return (
      <div className="page">
        <PageHeader eyebrow="Semantic" title="Semantic" />
        <EmptyState icon={Scale} title="Connect your data first"
          description="Business metrics are proposed from your ontology. Connect your data on the Ontology page first."
          action={<Button variant="primary" icon={<Plus size={15} />} onClick={() => navigate('/tools/ontology/new')}>Connect data</Button>} />
      </div>
    )
  }
  if (!oid) return <div className="page"><LoadingState label="Opening" /></div>
  const current = ontologies.find((o) => o.id === oid)
  if (!current) {
    return (
      <div className="page">
        <PageHeader eyebrow="Semantic" title="Semantic" />
        <EmptyState icon={SearchX} title="This data is no longer here" description={<>There is nothing called <code>{oid}</code>.</>}
          action={<Button variant="primary" onClick={() => navigate('/tools/semantic', { replace: true })}>Open the latest</Button>} />
      </div>
    )
  }
  return (
    <Workspace key={oid} oid={oid} name={current.name}
      choices={ontologies.map((o) => ({ id: o.id, name: o.name }))}
      onSwitch={(id) => navigate(`/tools/semantic/${encodeURIComponent(id)}`)} />
  )
}

const fmt = (v: number | null, unit?: string | null) => (v === null || v === undefined ? '–' : `${compact(v)}${unit ? ` ${unit}` : ''}`)

function Workspace({ oid, name, choices, onSwitch }: {
  oid: string
  name: string
  choices: Array<{ id: string; name: string }>
  onSwitch: (id: string) => void
}) {
  const [tick, setTick] = useState(0)
  const state = useAsync((signal) => api.semOverview(oid, signal), [oid, tick])
  const [open, setOpen] = useState<string | null>(null)
  const reload = () => setTick((t) => t + 1)

  if (state.initialLoading && !state.data) return <div className="page"><LoadingState label="Working out your business metrics" /></div>
  if (!state.data) {
    const msg = describeError(state.error).message
    return (
      <div className="page">
        <PageHeader eyebrow="Semantic" title={name} />
        {/no route|older version/i.test(msg)
          ? <EmptyState icon={Scale} title="Restart the server" description="The server is older than this page. Stop it (Ctrl+C) and start it again with python run_server.py." />
          : <ErrorState error={state.error} onRetry={state.reload} />}
      </div>
    )
  }
  const o = state.data
  const certified = o.metrics.filter((m) => m.status === 'certified')
  const proposed = o.metrics.filter((m) => m.status === 'proposed')

  return (
    <div className="page">
      <PageHeader eyebrow="Semantic" title={name}
        description="One governed number per business word, computed the same way everywhere: screens, agents and Excel."
        actions={choices.length > 1 ? (
          <select className="input" value={oid} aria-label="Choose data" onChange={(e) => onSwitch(e.target.value)}>
            {choices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        ) : null} />


      <p className="sem-summary">
        <span><BadgeCheck size={15} aria-hidden="true" /> <b>{o.summary.certified}</b> certified</span>
        <span><CircleHelp size={15} aria-hidden="true" /> <b>{o.summary.proposed}</b> proposed</span>
        {o.summary.drift ? <span className="is-warn"><TriangleAlert size={15} aria-hidden="true" /> <b>{o.summary.drift}</b> to check</span> : null}
      </p>

      {o.decisions.map((d) => <Decision key={d.word} oid={oid} d={d} onDone={(n) => { reload(); setOpen(n) }} />)}

      {open ? <MetricPanel key={open} oid={oid} name={open} onClose={() => setOpen(null)} onChange={reload} /> : null}

      {certified.length ? <h2 className="sem-h">Certified</h2> : null}
      <section className="sem-grid">{certified.map((m) => <MetricCard key={m.name} m={m} active={open === m.name} onOpen={() => setOpen(m.name)} />)}</section>
      {proposed.length ? <h2 className="sem-h">Proposed from your ontology</h2> : null}
      <section className="sem-grid">{proposed.map((m) => <MetricCard key={m.name} m={m} active={open === m.name} onOpen={() => setOpen(m.name)} />)}</section>

      <AddInWords oid={oid} refresh={o.metrics.length} onAdded={(n) => { reload(); setOpen(n) }} />

      <TrustPanel oid={oid} layer="semantic" here={['semantic']} />
      <UseElsewhere layer="semantic" oid={oid} />
    </div>
  )
}

function MetricCard({ m, active, onOpen }: { m: SemCard; active: boolean; onOpen: () => void }) {
  const spark = useMemo(() => (m.trend.length > 2 ? sparkOption(m.trend) : null), [m.trend])
  const proof = m.drift.length ? 'disagrees' : m.status === 'certified' ? 'person' : 'guess'
  const proofLabel = m.drift.length ? 'Needs a check' : m.status === 'certified'
    ? (m.owner ? `Certified by ${m.owner}` : 'Certified') : 'AI draft'
  return (
    <button type="button" className={cx('sem-card', active && 'is-active', m.drift.length > 0 && 'is-drift')} onClick={onOpen}>
      <span className="sem-card__top">
        <span className="sem-card__title">{m.title}</span>
        <ProofMark kind={proof} size="sm" label={proofLabel} />
      </span>
      {m.company_meaning ? (
        <ProofMark kind="company" size="sm" label="Company meaning" detail={m.company_meaning}
          className="sem-card__delta" />
      ) : null}
      <span className="sem-card__value">{fmt(m.value, m.unit)}</span>
      {spark ? <EChart option={spark} ariaLabel={`${m.title} trend`} height={44} /> : <span className="sem-card__nospark" />}
      {m.synonyms.length ? <span className="sem-card__also">also: {m.synonyms.slice(0, 3).join(', ')}</span> : null}
    </button>
  )
}

function Decision({ oid, d, onDone }: { oid: string; d: SemDecision; onDone: (name: string) => void }) {
  const toast = useToast()
  const [busy, setBusy] = useState<string | null>(null)
  const values = d.candidates.filter((c) => c.value !== null)
  const option = useMemo(() => chartOption('bar', values.map((c) => c.title), values.map((c) => c.value as number), '', true), [values])
  const pick = async (name: string) => {
    setBusy(name)
    try {
      await api.semDecide(oid, d.word, name)
      toast.push({ title: 'Decided', message: `This is ${d.word} now, everywhere.`, tone: 'success' })
      onDone(name)
    } catch (e) {
      toast.push({ title: 'Not saved', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(null)
    }
  }
  return (
    <section className="sem-decision" aria-label={`Decide ${d.word}`}>
      <h2><Scale size={18} aria-hidden="true" /> {d.question}</h2>
      <p className="kg-muted">Each bar is a different total someone could call {d.word}. Pick once; every screen, agent and spreadsheet then uses that one.</p>
      <EChart option={option} ariaLabel={`Candidates for ${d.word}`} height={Math.max(160, values.length * 36)} />
      <div className="sem-decision__picks">
        {d.candidates.map((c) => (
          <div key={c.name} className="sem-pick">
            <div><strong>{c.title}</strong><span className="kg-muted">{c.words}</span></div>
            <Button size="sm" variant="secondary" loading={busy === c.name} disabled={Boolean(busy)} onClick={() => void pick(c.name)}>
              This one is {d.word}
            </Button>
          </div>
        ))}
      </div>
    </section>
  )
}

function MetricPanel({ oid, name, onClose, onChange }: { oid: string; name: string; onClose: () => void; onChange: () => void }) {
  const toast = useToast()
  const [by, setBy] = useState<string | null>(null)
  const state = useAsync((signal) => api.semDetail(oid, name, by, signal), [oid, name, by])
  const [owner, setOwner] = useState('')
  const [word, setWord] = useState('')
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const m = state.data
  const breakdown = useMemo(() => {
    if (!m?.breakdown?.rows.length) return null
    const rows = m.breakdown.rows.filter((r) => r[1] !== null)
    const x = rows.map((r) => String(r[0] ?? '(empty)'))
    return chartOption('bar', x, rows.map((r) => Number(r[1])), m.unit ?? '', x.length > 8 || x.some((s) => s.length > 14))
  }, [m])
  const trend = useMemo(() => (m && m.trend.length > 2
    ? chartOption('line', m.trend.map((p) => p.period.slice(0, 7)), m.trend.map((p) => Number(p.value ?? 0)), m.unit ?? '')
    : null), [m])

  const act = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true)
    try {
      await fn()
      toast.push({ title: done, tone: 'success' })
      onChange()
      state.reload()
    } catch (e) {
      toast.push({ title: 'Not saved', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  if (!m) return <section className="sem-panel">{state.error ? <ErrorState error={state.error} onRetry={state.reload} /> : <LoadingState label="Opening" />}</section>
  const dimLabel = (n: string | null) => m.dims.find((d) => d.name === n)?.label ?? n ?? ''
  return (
    <section className="sem-panel" aria-label={m.title}>
      <div className="sem-panel__head">
        <div>
          <p className="sem-eyebrow">{m.thing}</p>
          <h2>{m.title} <span className={cx('sem-status', `is-${m.drift.length ? 'drift' : m.status}`)}>{m.drift.length ? 'Check' : m.status === 'certified' ? 'Certified' : 'Proposed'}</span></h2>
          <p className="sem-panel__value">{fmt(m.value, m.unit)}</p>
        </div>
        <button type="button" className="cx-answer__close" aria-label="Close" onClick={onClose}><X size={18} /></button>
      </div>

      {m.drift.length ? (
        <p className="kgb__error"><TriangleAlert size={15} aria-hidden="true" /> The data under this metric changed since it was certified: {m.drift.join('; ')}.</p>
      ) : null}

      <div className="sem-panel__charts">
        <div>
          <div className="sem-chips">
            {m.dims.map((d) => (
              <button key={d.name} type="button" className={cx(d.name === m.by && 'is-on')} onClick={() => setBy(d.name)}>by {d.label}</button>
            ))}
          </div>
          {breakdown ? <EChart option={breakdown} ariaLabel={`${m.title} by ${dimLabel(m.by)}`} height={260} /> : <p className="kg-muted">No breakdown for this metric.</p>}
        </div>
        <div>
          <p className="sem-chart-title">Over time{m.receipt.time ? ` (by ${m.receipt.time})` : ''}</p>
          {trend ? <EChart option={trend} ariaLabel={`${m.title} over time`} height={260} /> : <p className="kg-muted">No date to draw a trend.</p>}
        </div>
      </div>

      <div className="sem-receipt">
        <h3>How this number is computed</h3>
        <p>{m.receipt.words}</p>
        <dl>
          <div><dt>Formula</dt><dd><code>{m.receipt.formula}</code></dd></div>
          {m.receipt.filters.length ? <div><dt>Only</dt><dd>{m.receipt.filters.join('; ')}</dd></div> : null}
          {m.receipt.joins.length ? <div><dt>Joins</dt><dd>{m.receipt.joins.join('; ')}. <span className="kg-muted">{m.receipt.safe_joins}</span></dd></div> : null}
          <div><dt>Owner</dt><dd>{m.receipt.owner ?? '–'}</dd></div>
          <div><dt>Certified</dt><dd>{m.receipt.certified_at ? `${m.receipt.certified_at.slice(0, 10)}${m.receipt.certified_by ? ` by ${m.receipt.certified_by}` : ''}` : 'not yet'}</dd></div>
          <div><dt>Also called</dt><dd>{m.synonyms.length ? m.synonyms.join(', ') : '–'}</dd></div>
        </dl>
        <details className="cx-details"><summary><ChevronDown size={14} aria-hidden="true" /> The SQL</summary><pre className="ctx-pack">{m.receipt.sql}</pre></details>
      </div>

      {m.verified.length ? (
        <ul className="sem-verified">
          {m.verified.map((v) => (
            <li key={v.key} className={v.passed ? 'is-ok' : 'is-bad'}>
              {v.passed ? <BadgeCheck size={14} aria-hidden="true" /> : <TriangleAlert size={14} aria-hidden="true" />} {v.question}
              {v.why ? <span className="kg-muted"> · {v.why}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}

      <WhatDepends key={name} oid={oid} kind="metric" target={name} />

      <div className="sem-actions">
        {m.status !== 'certified' || m.drift.length ? (
          <div className="sem-inline">
            <input className="input" value={owner} placeholder="Owner (optional), e.g. Finance" aria-label="Owner" onChange={(e) => setOwner(e.target.value)} />
            <Button variant="primary" loading={busy} onClick={() => void act(() => api.semCertify(oid, name, owner), 'Certified')}>
              {m.drift.length ? 'Re-certify' : 'Certify'}
            </Button>
          </div>
        ) : null}
        <div className="sem-inline">
          <input className="input" value={word} placeholder="Another name for it, e.g. sales" aria-label="Another name" onChange={(e) => setWord(e.target.value)} />
          <Button variant="secondary" disabled={!word.trim() || busy} onClick={() => void act(() => api.semSynonym(oid, name, word.trim()).then(() => setWord('')), 'Name added')}>Add name</Button>
        </div>
        <div className="sem-inline">
          <input className="input" value={question} placeholder={`A question this answers, e.g. ${m.title} by ${dimLabel(m.by) || 'month'}`} aria-label="Verified question" onChange={(e) => setQuestion(e.target.value)} />
          <Button variant="secondary" disabled={!question.trim() || busy} onClick={() => void act(() => api.semVerified(oid, name, question.trim(), m.by).then(() => setQuestion('')), 'Saved; it is re-checked after every rebuild')}>Save as verified</Button>
        </div>
        {m.status !== 'retired' ? (
          <button type="button" className="sem-link" disabled={busy} onClick={() => void act(() => api.semRetire(oid, name).then(onClose), 'Retired')}>Retire this metric</button>
        ) : null}
      </div>
    </section>
  )
}

function AddInWords({ oid, refresh, onAdded }: { oid: string; refresh: number; onAdded: (name: string) => void }) {
  const toast = useToast()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const sugg = useSuggestions(oid, 'metric', refresh)
  const add = async () => {
    setBusy(true)
    try {
      const m = await api.semWords(oid, text.trim())
      toast.push({ title: 'Proposed', message: `${m.title}: ${fmt(m.value, m.unit)}. Check it, then certify.`, tone: 'success' })
      setText('')
      onAdded(m.name)
    } catch (e) {
      toast.push({ title: 'Not added', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="sem-words">
    <h2 className="sem-h">Add a metric in words</h2>
    <form className="cx-ask" onSubmit={(e) => { e.preventDefault(); void add() }}>
      <Sparkles size={18} aria-hidden="true" />
      <input value={text} aria-label="Define a metric in words" maxLength={1000}
        placeholder={`e.g. ${sugg.items[0]?.text ?? 'Revenue is the total payment value of delivered orders'}`}
        onChange={(e) => setText(e.target.value)} />
      <Button type="submit" variant="primary" loading={busy} disabled={!text.trim()}>Add metric</Button>
    </form>
    <SuggestionChips s={sugg} detailed disabled={busy} label="Suggested metrics" onPick={setText} />
    </section>
  )
}
