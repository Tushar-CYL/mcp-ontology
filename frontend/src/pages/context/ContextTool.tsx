import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowRight, ChevronDown, CircleCheck, MessageSquareWarning, Plus, SearchX, Sparkles, TriangleAlert } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { CtxBuild, CtxChart, CtxFact } from '../../api/types'
import { ProofMark, type Proof } from '../../components/ProofMark'
import { EvidenceDrawer, type Evidence } from '../../components/EvidenceDrawer'
import { Button } from '../../components/Button'
import { EChart } from '../../components/EChart'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { Disclose } from '../../components/Disclose'
import { UseElsewhere } from '../../components/UseElsewhere'
import { SuggestionChips } from '../../components/SuggestionChips'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useSuggestions } from '../../hooks/useSuggestions'
import { cx } from '../../utils/cx'
import { chartOption, compact, headline, shapeOf } from './charts'
import { Gaps } from './Gaps'

/**
 * Context, picture first: the data at a glance as charts, a question picked
 * from them (or typed), and the answer as a chart. How the answer was built
 * (Nehme's method: link, follow the graph, check the facts) sits in one line
 * underneath, with the detail one click away.
 */
export function ContextTool() {
  useDocumentTitle('Context')
  const { oid } = useParams()
  const navigate = useNavigate()
  const list = useAsync((signal) => api.ontoList(signal), [])
  const ontologies = useMemo(() => list.data?.ontologies ?? [], [list.data])

  useEffect(() => {
    if (oid || !ontologies.length) return
    const latest = [...ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    navigate(`/tools/context/${encodeURIComponent(latest.id)}`, { replace: true })
  }, [oid, ontologies, navigate])

  if (list.initialLoading && !list.data) return <div className="page"><LoadingState label="Loading" /></div>
  if (list.error) return <div className="page"><ErrorState error={list.error} onRetry={list.reload} /></div>
  if (!ontologies.length) {
    return (
      <div className="page">
        <PageHeader eyebrow="Context" title="Context" />
        <EmptyState icon={Sparkles} title="Connect your data first"
          description="Connect your data on the Ontology page; its charts and questions appear here."
          action={<Button variant="primary" icon={<Plus size={15} />} onClick={() => navigate('/tools/ontology/new')}>Connect data</Button>} />
      </div>
    )
  }
  if (!oid) return <div className="page"><LoadingState label="Opening" /></div>
  const current = ontologies.find((o) => o.id === oid)
  if (!current) {
    return (
      <div className="page">
        <PageHeader eyebrow="Context" title="Context" />
        <EmptyState icon={SearchX} title="This data is no longer here"
          description={<>There is nothing called <code>{oid}</code>.</>}
          action={<Button variant="primary" onClick={() => navigate('/tools/context', { replace: true })}>Open the latest</Button>} />
      </div>
    )
  }
  return (
    <Workspace key={oid} oid={oid} name={current.name}
      choices={ontologies.map((o) => ({ id: o.id, name: o.name }))}
      onSwitch={(id) => navigate(`/tools/context/${encodeURIComponent(id)}`)} />
  )
}

function Workspace({ oid, name, choices, onSwitch }: {
  oid: string
  name: string
  choices: Array<{ id: string; name: string }>
  onSwitch: (id: string) => void
}) {
  const glance = useAsync((signal) => api.ctxInsights(oid, signal), [oid])
  const sugg = useSuggestions(oid, 'ask')
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [out, setOut] = useState<CtxBuild | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [asked, setAsked] = useState(0)

  const ask = async (q = question) => {
    const text = q.trim()
    if (!text) return
    setQuestion(text)
    setBusy(true)
    setError(null)
    try {
      const built = await api.ctxBuild(oid, text)
      setOut(built)
      if (built.gap) setAsked((n) => n + 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) {
      const msg = describeError(e).message
      setError(/no route|older version/i.test(msg)
        ? 'The server is older than this page. Stop it (Ctrl+C) and start it again with python run_server.py.'
        : msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <PageHeader eyebrow="Context" title={name}
        description="Your data at a glance. Pick a question, or ask your own."
        actions={choices.length > 1 ? (
          <select className="input" value={oid} aria-label="Choose data" onChange={(e) => onSwitch(e.target.value)}>
            {choices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        ) : null} />


      <form className="cx-ask" onSubmit={(e) => { e.preventDefault(); void ask() }}>
        <Sparkles size={18} aria-hidden="true" />
        <input value={question} aria-label="Question" maxLength={1000}
          placeholder="Ask anything about this data" onChange={(e) => setQuestion(e.target.value)} />
        <Button type="submit" variant="primary" loading={busy} disabled={!question.trim()}>Ask</Button>
      </form>
      <SuggestionChips label="Suggested questions" disabled={busy} onPick={(q) => void ask(q)}
        s={sugg.items.length || sugg.improving ? sugg
          : { items: (glance.data?.questions ?? []).map((q) => ({ text: q, why: 'From the charts below' })),
              method: 'data', improving: false }} />
      {error ? <p className="kgb__error"><TriangleAlert size={15} aria-hidden="true" /> {error}</p> : null}

      {out ? <AnswerPanel oid={oid} out={out} onClose={() => setOut(null)} /> : null}
      {out?.gap ? (
        <p className="cx-gapnote"><TriangleAlert size={14} aria-hidden="true" /> Logged under “Questions it could not answer” below: {out.gap.label.toLowerCase()}.</p>
      ) : null}

      {glance.initialLoading && !glance.data ? <LoadingState label="Reading your data" /> : null}
      {glance.error && !glance.data ? <ErrorState error={glance.error} onRetry={glance.reload} /> : null}
      {glance.data ? (
        <>
          <section className="cx-kpis" aria-label="Key numbers">
            {glance.data.kpis.map((k) => (
              <button key={k.label} type="button" className="cx-kpi" onClick={() => void ask(k.question)}
                title={`Ask: ${k.question}`}>
                <span className="cx-kpi__value">{compact(k.value)}{k.unit ? <small> {k.unit}</small> : null}</span>
                <span className="cx-kpi__label">{k.label}</span>
              </button>
            ))}
          </section>
          <section className="cx-grid" aria-label="Charts">
            {glance.data.charts.map((c) => <ChartCard key={c.id} c={c} onAsk={() => void ask(c.question)} busy={busy} />)}
          </section>
        </>
      ) : null}

      <section className="cx-proof" aria-label="Gaps">
        <Disclose summary="Questions it could not answer"
          note={asked ? `${asked} logged` : 'None logged yet'}>
          <Gaps oid={oid} refresh={asked} />
        </Disclose>
      </section>

      <UseElsewhere layer="context" oid={oid} />
    </div>
  )
}

function ChartCard({ c, onAsk, busy }: { c: CtxChart; onAsk: () => void; busy: boolean }) {
  const option = useMemo(() => chartOption(c.kind, c.x, c.y, c.y_label, c.horizontal), [c])
  return (
    <article className="cx-card">
      <header>
        <h3>{c.title}</h3>
        {c.subtitle ? <p>{c.subtitle}</p> : null}
      </header>
      <EChart option={option} ariaLabel={`${c.title}: ${c.x.slice(0, 5).map((x, i) => `${x} ${c.y[i]}`).join(', ')}`}
        height={c.horizontal ? Math.max(220, c.x.length * 26) : 240} />
      <button type="button" className="cx-card__ask" onClick={onAsk} disabled={busy}>
        <ArrowRight size={13} aria-hidden="true" /> {c.question}
      </button>
    </article>
  )
}

const VERDICT: Record<CtxBuild['steps']['answer']['status'], string> = {
  answered: 'Answered from checked facts',
  not_enough: 'Not enough evidence',
  unverified: 'Rejected: the answer used numbers not in the data',
  no_ai: 'Facts ready (no AI configured to write the answer)',
  ai_busy: 'The AI is busy; facts are ready',
  ai_error: 'The AI did not answer; facts are ready',
}

function AnswerPanel({ oid, out, onClose }: { oid: string; out: CtxBuild; onClose: () => void }) {
  const s = out.steps
  const [ev, setEv] = useState<Evidence | null>(null)
  const table = s.facts.table
  const shape = table ? shapeOf(table.columns, table.rows) : null
  // A record question has no table: show what the record is connected to,
  // per kind of thing - or per kind of link when every record has one type.
  const first = !table ? s.follow.walks[0]?.steps[0] : undefined
  const reach = first
    ? (first.reached.length > 1 || !first.by_link?.length
      ? first.reached.map((r) => ({ name: r.thing, count: r.count }))
      : first.by_link.map((r) => ({ name: r.link, count: r.count })))
    : undefined
  const option = useMemo(() => {
    if (shape && (shape.kind === 'bar' || shape.kind === 'line')) {
      return chartOption(shape.kind, shape.x, shape.y, shape.yLabel, shape.horizontal)
    }
    if (reach && reach.length) {
      return chartOption('bar', reach.map((r) => r.name), reach.map((r) => r.count), 'records',
        reach.length > 6 || reach.some((r) => r.name.length > 14))
    }
    return null
  }, [shape, reach])
  const understood = [
    ...s.understand.records.map((r) => r.label ?? r.key),
    ...(s.understand.values ?? []).map((v) => `${v.label} = ${v.value}`),
    ...s.understand.fields.slice(0, 3).map((f) => f.label),
  ]
  const followed = s.follow.in_scope
  const leftOut = s.facts.quarantined.length + (s.answer.unsupported_numbers?.length ?? 0)

  return (
    <section className={cx('cx-answer', `is-${s.answer.status}`)} aria-label="Answer">
      <div className="cx-answer__head">
        <p className="cx-answer__q">{out.question}</p>
        <button type="button" className="cx-answer__close" onClick={onClose} aria-label="Close the answer">×</button>
      </div>

      {understood.length ? (
        <div className="answercard__read" aria-label="How the question was read">
          <span className="kg-muted">I read it as</span>
          {understood.slice(0, 5).map((u, i) => <span key={`${u}-${i}`} className="readchip">{u}</span>)}
        </div>
      ) : null}

      {shape?.kind === 'number' ? (
        <div className="cx-hero">
          <span className="cx-hero__value">{typeof shape.value === 'number' ? shape.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : shape.value}</span>
          <span className="cx-hero__label">{shape.label.replace(/_/g, ' ')}</span>
        </div>
      ) : null}
      {shape && headline(shape) && s.answer.status !== 'not_enough' ? (
        <p className="cx-answer__text">{headline(shape)}</p>
      ) : s.answer.status === 'answered' || s.answer.status === 'not_enough' ? (
        <p className="cx-answer__text">{s.answer.text.replace(/\s*\[\d+\]/g, '').replace(/\*\*|__|`/g, '')}</p>
      ) : (
        <p className="cx-answer__text is-muted">{VERDICT[s.answer.status]}{s.answer.warning ? ` · ${s.answer.warning}` : ''}</p>
      )}
      {option ? (
        <EChart option={option} ariaLabel={`Answer chart for: ${out.question}`}
          height={shape && shape.kind === 'bar' && shape.horizontal ? Math.max(220, shape.x.length * 26) : 260} />
      ) : null}
      {reach && reach.length ? <p className="kg-muted">Records linked to {s.follow.walks[0].from.label}</p> : null}

      {s.facts.kept.length ? (
        <div className="answercard__facts" aria-label="The facts behind this answer">
          {s.facts.kept.slice(0, 6).map((f, i) => (
            <button key={`${f.citation ?? f.text}-${i}`} type="button" className="factchip"
              onClick={() => setEv(factEvidence(out.question, f))}>
              <span>{f.text}</span>
              <ProofMark kind={factProof(f.kind)} size="sm" />
            </button>
          ))}
        </div>
      ) : null}
      {leftOut ? (
        <p className="answercard__left-out"><TriangleAlert size={14} aria-hidden="true" />
          I left out {leftOut === 1 ? '1 thing' : `${leftOut} things`} I could not prove.</p>
      ) : null}

      <div className="cx-trail" aria-label="How this answer was built">
        <span className={cx('cx-badge', s.answer.status === 'answered' ? 'is-ok' : 'is-warn')}>
          {s.answer.status === 'answered' ? <CircleCheck size={13} aria-hidden="true" /> : <TriangleAlert size={13} aria-hidden="true" />}
          {VERDICT[s.answer.status]}
        </span>
        {understood.length ? <span>Understood: <b>{understood.slice(0, 4).join(', ')}</b></span> : null}
        {followed.length ? <span>Looked at: <b>{followed.slice(0, 4).join(' · ')}</b></span> : null}
        <span>{s.facts.kept.length} facts checked</span>
      </div>

      <details className="cx-details">
        <summary><ChevronDown size={14} aria-hidden="true" /> What the AI saw</summary>
        <pre className="ctx-pack">{out.context || '(no facts)'}</pre>
        {s.facts.quarantined.length ? (
          <p className="kg-muted">Held back: {s.facts.quarantined.map((q) => `${q.what} (${q.why})`).join('; ')}</p>
        ) : null}
        {s.follow.not_looked_at.length ? <p className="kg-muted">Not looked at: {s.follow.not_looked_at.join(', ')}</p> : null}
        {s.understand.unknown.length ? <p className="kg-muted">Words not understood: {s.understand.unknown.join(', ')}</p> : null}
        {s.facts.sql ? <pre className="ctx-pack">{s.facts.sql}</pre> : null}
        <p className="kg-muted">Ontology version {out.ontology.version ?? '-'}{out.data_as_of ? ` · data as of ${out.data_as_of.slice(0, 16).replace('T', ' ')}` : ''}</p>
        <Feedback oid={oid} question={out.question} />
      </details>

      <p className="answercard__scope">I can show the facts and rules I used, not how the AI chose its words.</p>
      <EvidenceDrawer evidence={ev} onClose={() => setEv(null)} />
    </section>
  )
}

// Which proof mark a context fact carries, from the kind of fact it is.
const FACT_PROOF: Record<string, Proof> = {
  count: 'proved', number: 'proved', check: 'proved', record: 'proved',
  link: 'proved', meaning: 'proved', rule: 'rule', note: 'person',
}
const factProof = (kind: string): Proof => FACT_PROOF[kind] ?? 'guess'

function factEvidence(question: string, f: CtxFact): Evidence {
  const rows: Array<{ k: string; v: string }> = [{ k: 'Where it came from', v: f.source }]
  if (f.citation) rows.push({ k: 'Reference', v: f.citation })
  if (f.reason) rows.push({ k: 'Why it was used', v: f.reason })
  return { title: question, proof: factProof(f.kind), statement: f.text, rows }
}

function Feedback({ oid, question }: { oid: string; question: string }) {
  const toast = useToast()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const send = async () => {
    setBusy(true)
    try {
      await api.ctxFeedback(oid, question, text)
      toast.push({ title: 'Saved', message: 'The next answer uses your note.', tone: 'success' })
      setText('')
    } catch (e) {
      toast.push({ title: 'Not saved', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="ctx-feedback">
      <MessageSquareWarning size={16} aria-hidden="true" />
      <input className="input" value={text} aria-label="Answer wrong? Tell us why" maxLength={2000}
        placeholder="Answer wrong? Tell us why" onChange={(e) => setText(e.target.value)} />
      <Button size="sm" variant="secondary" loading={busy} disabled={!text.trim()} onClick={send}>Save</Button>
    </div>
  )
}
