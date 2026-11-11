import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, Check, CircleCheck, CircleDashed, Copy, Download, FileJson, GitBranch, KeyRound,
  Link2, MessageSquarePlus, Pencil, RefreshCw, Search, Send, Share2, Table2,
  TriangleAlert, X,
} from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { EoJob, OntoAsk, OntoCheck, OntoField, OntoThing, OntoView as View } from '../../api/types'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { cx } from '../../utils/cx'
import {
  CHECK, SET_BY, centralThing, checkedShare, conflictCount, filterFields, filterThings,
  formatCount, matchLabel,
} from '../../utils/onto'
import { DeleteOntology } from './DeleteOntology'
import { OntoMap } from './OntoMap'
import { JobLog } from './shared'

export type Tab = 'overview' | 'map' | 'ask' | 'use'

const CHECK_ICON: Record<OntoCheck, typeof CircleCheck> = {
  verified: CircleCheck, conflict: TriangleAlert, unchecked: CircleDashed,
}

/** The ontology: overview (things and fields), map, and how to use it. */
export function OntologyView({ view, tab, onTab, onChange, onDeleted }: {
  view: View
  tab: Tab
  onTab: (tab: Tab) => void
  onChange: (next?: View) => void
  onDeleted: () => void
}) {
  const toast = useToast()
  const [jobId, setJobId] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [onlyConflicts, setOnlyConflicts] = useState(false)
  const conflicts = view.summary.checks.conflict ?? 0

  const rebuild = async () => {
    try {
      setJobId((await api.ontoRebuild(view.id)).job_id)
    } catch (e) {
      toast.push({ title: 'Could not rebuild', message: describeError(e).message, tone: 'error' })
    }
  }

  return (
    <div className="onto">
      <section className="onto-summary" aria-label="Summary">
        <Metric value={formatCount(view.summary.things)} label="Business things" />
        <Metric value={formatCount(view.summary.fields)} label="Fields explained" />
        <Metric value={formatCount(view.summary.links)} label="Links proven" />
        <Metric value={`${checkedShare(view.summary)}%`} label="Confirmed by the data" />
        {conflicts ? (
          <button type="button" className="onto-summary__alert"
            onClick={() => { setOnlyConflicts(true); onTab('overview') }}>
            <TriangleAlert size={16} aria-hidden="true" />
            <span><strong>{conflicts}</strong> {conflicts === 1 ? 'field needs' : 'fields need'} a look</span>
          </button>
        ) : (
          <span className="onto-summary__ok"><CircleCheck size={16} aria-hidden="true" /> Nothing to fix</span>
        )}
        <div className="onto-summary__actions">
          <Button size="sm" variant="ghost" icon={<RefreshCw size={14} />} onClick={rebuild}
            disabled={Boolean(jobId)}>Rebuild</Button>
          <DeleteOntology id={view.id} name={view.name} onDeleted={onDeleted} />
        </div>
      </section>

      {jobId ? (
        <Card title="Rebuilding" subtitle="Your corrections and notes are kept.">
          <JobLog jobId={jobId} onFinished={(job: EoJob) => {
            setJobId(null)
            onChange()
            toast.push({ title: job.status === 'done' ? 'Rebuilt' : 'Rebuild failed',
              message: job.error ?? undefined, tone: job.status === 'done' ? 'success' : 'error' })
          }} />
        </Card>
      ) : null}

      <nav className="onto-tabs" role="tablist" aria-label="Views">
        {([['overview', 'Overview', Table2], ['map', 'Map', Share2], ['ask', 'Ask', MessageSquarePlus],
          ['use', 'Use it', ArrowRight]] as const)
          .map(([id, label, Icon]) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id}
              className={cx('onto-tab', tab === id && 'is-active')} onClick={() => onTab(id)}>
              <Icon size={15} aria-hidden="true" /> {label}
            </button>
          ))}
      </nav>

      {tab === 'overview' ? (
        <Explorer view={view} selected={selected} onSelect={setSelected}
          onlyConflicts={onlyConflicts} onOnlyConflicts={setOnlyConflicts} onChange={onChange} />
      ) : null}
      {tab === 'map' ? (
        <OntoMap view={view} selected={view.things.find((t) => t.key === selected)?.name}
          onOpen={(key) => { setSelected(key); onTab('overview') }} />
      ) : null}
      {tab === 'ask' ? <AskPanel view={view} /> : null}
      {tab === 'use' ? <UseIt view={view} /> : null}
    </div>
  )
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="onto-metric">
      <span className="onto-metric__value">{value}</span>
      <span className="onto-metric__label">{label}</span>
    </div>
  )
}

/* ------------------------------------------------------------------ overview */
function Explorer({ view, selected, onSelect, onlyConflicts, onOnlyConflicts, onChange }: {
  view: View
  selected: string | null
  onSelect: (key: string) => void
  onlyConflicts: boolean
  onOnlyConflicts: (on: boolean) => void
  onChange: (next?: View) => void
}) {
  const [query, setQuery] = useState('')
  const things = filterThings(view.things, query)
  const central = useMemo(() => centralThing(view), [view])
  const firstConflict = view.things.find((t) => conflictCount(t) > 0)
  const current = view.things.find((t) => t.key === selected)
    ?? (onlyConflicts ? firstConflict : undefined) ?? (query ? things[0] : view.things.find((t) => t.name === central))
    ?? things[0] ?? view.things[0]

  return (
    <div className="onto-explorer">
      <aside className="onto-list" aria-label="Business things">
        <div className="onto-list__search">
          <Search size={15} aria-hidden="true" />
          <input value={query} placeholder="Search things and fields" aria-label="Search things and fields"
            onChange={(e) => setQuery(e.target.value)} />
          {query ? <button type="button" aria-label="Clear search" onClick={() => setQuery('')}><X size={14} /></button> : null}
        </div>
        <p className="onto-list__count">{things.length} of {view.things.length} things</p>
        <ul>
          {things.map((t) => {
            const bad = conflictCount(t)
            return (
              <li key={t.key}>
                <button type="button" className={cx('onto-list__item', current?.key === t.key && 'is-active')}
                  onClick={() => onSelect(t.key)} aria-current={current?.key === t.key ? 'true' : undefined}>
                  <span className="onto-list__text">
                    <span className="onto-list__name">{t.name}</span>
                    <span className="onto-list__meta">{t.fields.length} fields{t.records ? ` · ${formatCount(t.records)}` : ''}</span>
                  </span>
                  {bad ? <span className="onto-list__warn" title={`${bad} to check`}>{bad}</span> : null}
                </button>
              </li>
            )
          })}
          {!things.length ? <li className="onto-list__empty">Nothing matches “{query}”.</li> : null}
        </ul>
      </aside>

      <div className="onto-detail">
        {current ? (
          <ThingDetail key={current.key} view={view} thing={current} query={query}
            onlyConflicts={onlyConflicts} onOnlyConflicts={onOnlyConflicts} onChange={onChange}
            onOpen={(name) => { const t = view.things.find((x) => x.name === name); if (t) onSelect(t.key) }} />
        ) : <Card><p className="muted">No business things found.</p></Card>}
      </div>

      <aside className="onto-aside">
        <ContextBox view={view} onChange={onChange} />
        {view.findings.length ? (
          <Card title="Worth knowing" bodyPadding="compact">
            <ul className="onto-bullets">
              {view.findings.map((f, i) => <li key={i}>{f.detail}</li>)}
            </ul>
          </Card>
        ) : null}
      </aside>
    </div>
  )
}

function ThingDetail({ view, thing, query, onlyConflicts, onOnlyConflicts, onChange, onOpen }: {
  view: View
  thing: OntoThing
  query: string
  onlyConflicts: boolean
  onOnlyConflicts: (on: boolean) => void
  onChange: (next?: View) => void
  onOpen: (thingName: string) => void
}) {
  const toast = useToast()
  const [sub, setSub] = useState<'fields' | 'links'>('fields')
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(thing.name)
  const [description, setDescription] = useState(thing.description)
  const [editing, setEditing] = useState<string | null>(null)
  const fields = filterFields(thing.fields, query, onlyConflicts)
  const links = view.links.filter((l) => l.from_thing === thing.name || l.to_thing === thing.name)
  const calcs = view.calculations.filter((c) => c.thing === thing.name)
  const bad = conflictCount(thing)

  const saveThing = async () => {
    try {
      onChange(await api.ontoEditThing(view.id, { key: thing.key, name, description }))
      setRenaming(false)
    } catch (e) {
      toast.push({ title: 'Not saved', message: describeError(e).message, tone: 'error' })
    }
  }

  return (
    <section className="onto-card" aria-label={thing.name}>
      <header className="onto-card__head">
        {renaming ? (
          <div className="onto-rename">
            <input className="input" value={name} aria-label="Name" onChange={(e) => setName(e.target.value)} />
            <textarea className="input input--area" rows={2} value={description} aria-label="Description"
              onChange={(e) => setDescription(e.target.value)} />
            <div className="onto-row">
              <Button size="sm" variant="primary" icon={<Check size={14} />} onClick={saveThing}>Save</Button>
              <Button size="sm" variant="ghost" onClick={() => setRenaming(false)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <>
            <div className="onto-card__title">
              <div>
                <h2>{thing.name}</h2>
                <p>{thing.description}</p>
              </div>
            </div>
            <Button size="sm" variant="ghost" icon={<Pencil size={14} />} onClick={() => setRenaming(true)}>Rename</Button>
          </>
        )}
      </header>
      <dl className="onto-facts">
        <div><dt>Records</dt><dd>{formatCount(thing.records)}</dd></div>
        <div><dt>Fields</dt><dd>{thing.fields.length}</dd></div>
        <div><dt>Links</dt><dd>{links.length}</dd></div>
        <div><dt>Source table</dt><dd>{thing.tables.map((t) => <code key={t}>{t}</code>)}</dd></div>
      </dl>

      <div className="onto-subtabs" role="tablist">
        <button type="button" role="tab" aria-selected={sub === 'fields'} className={cx(sub === 'fields' && 'is-active')}
          onClick={() => setSub('fields')}>Fields <span>{thing.fields.length}</span></button>
        <button type="button" role="tab" aria-selected={sub === 'links'} className={cx(sub === 'links' && 'is-active')}
          onClick={() => setSub('links')}>Links <span>{links.length}</span></button>
        {bad ? (
          <label className="onto-subtabs__filter">
            <input type="checkbox" checked={onlyConflicts} onChange={(e) => onOnlyConflicts(e.target.checked)} />
            Only fields to check ({bad})
          </label>
        ) : null}
      </div>

      {sub === 'fields' ? (
        <div className="onto-fields">
          <div className="onto-fields__head" aria-hidden="true">
            <span>Field</span><span>Meaning</span><span>Type</span><span>Data check</span><span />
          </div>
          {fields.map((f) => editing === f.key ? (
            <FieldEditor key={f.key} oid={view.id} field={f} roles={view.roles}
              onDone={(next) => { setEditing(null); if (next) onChange(next) }} />
          ) : (
            <FieldRow key={f.key} field={f} onEdit={() => setEditing(f.key)} onOpen={onOpen} />
          ))}
          {!fields.length ? <p className="onto-fields__empty">No field matches.</p> : null}
        </div>
      ) : (
        <ul className="onto-links">
          {links.map((l) => {
            const other = l.from_thing === thing.name ? l.to_thing : l.from_thing
            return (
              <li key={l.key}>
                <Link2 size={16} aria-hidden="true" />
                <div>
                  <button type="button" className="onto-links__title" onClick={() => onOpen(other)}>{l.label}</button>
                  <p>{l.triples != null
                    ? <span>{formatCount(l.triples)} times in the data{l.relation ? <> · <code>{l.relation}</code></> : null}</span>
                    : <><code>{l.from}</code> = <code>{l.to}</code></>}
                    {l.match != null ? <span className="onto-pill onto-pill--ok">{matchLabel(l.match)}</span> : null}
                    {l.declared ? <span className="onto-pill">from {l.declared}</span> : null}
                  </p>
                </div>
              </li>
            )
          })}
          {!links.length ? <li className="onto-fields__empty">{thing.name} is not linked to other things.</li> : null}
          {view.built?.hidden_relations ? (
            <li className="onto-links__more">
              Plus {formatCount(view.built.hidden_relations)} rarer relations
              ({formatCount(view.built.hidden_triples ?? 0)} triples) in the whole graph, counted but not listed.
            </li>
          ) : null}
        </ul>
      )}

      {calcs.length ? (
        <div className="onto-calcs">
          <h3>Calculations from your semantic model</h3>
          {calcs.map((c) => (
            <div key={c.name}><strong>{c.name}</strong><code>{c.expression}</code>{c.description ? <p>{c.description}</p> : null}</div>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function FieldRow({ field, onEdit, onOpen }: { field: OntoField; onEdit: () => void; onOpen: (thing: string) => void }) {
  const check = CHECK[field.check]
  const Icon = CHECK_ICON[field.check]
  return (
    <div className={cx('onto-field', `is-${field.check}`)}>
      <div className="onto-field__name">
        <span>{field.role === 'identifier' ? <KeyRound size={13} aria-label="Key" /> : null} {field.label}</span>
        <code>{field.column}</code>
      </div>
      <div className="onto-field__meaning">
        {field.meaning}
        {field.links_to ? (
          <button type="button" className="onto-field__link" onClick={() => onOpen(field.links_to!)}>
            <ArrowRight size={12} aria-hidden="true" /> {field.links_to}
          </button>
        ) : null}
      </div>
      <div className="onto-field__type">
        <span className="onto-pill">{field.role_label}</span>
        {field.unit ? <span className="onto-pill onto-pill--unit">{field.unit}</span> : null}
      </div>
      <div className="onto-field__check" title={check.hint}>
        <span className={`onto-check onto-check--${field.check}`}><Icon size={14} aria-hidden="true" /> {check.label}</span>
        {field.proof ? <span className="onto-field__proof">{field.proof}</span> : null}
        <span className="onto-field__by">Set by {SET_BY[field.by]}</span>
      </div>
      <div className="onto-field__edit">
        <button type="button" onClick={onEdit} aria-label={`Edit ${field.label}`}><Pencil size={14} /></button>
      </div>
    </div>
  )
}

function FieldEditor({ oid, field, roles, onDone }: {
  oid: string
  field: OntoField
  roles: Record<string, string>
  onDone: (next?: View) => void
}) {
  const toast = useToast()
  const [label, setLabel] = useState(field.label)
  const [meaning, setMeaning] = useState(field.meaning)
  const [role, setRole] = useState(field.role)
  const [unit, setUnit] = useState(field.unit ?? '')
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try {
      onDone(await api.ontoEditField(oid, { key: field.key, label, meaning, role, unit }))
      toast.push({ title: `Saved ${label}`, tone: 'success' })
    } catch (e) {
      toast.push({ title: 'Not saved', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="onto-field onto-field--editing">
      <div className="onto-field__name">
        <input className="input" value={label} aria-label="Field name" onChange={(e) => setLabel(e.target.value)} />
        <code>{field.column}</code>
      </div>
      <div className="onto-field__meaning">
        <textarea className="input input--area" rows={3} value={meaning} aria-label="Meaning"
          onChange={(e) => setMeaning(e.target.value)} />
      </div>
      <div className="onto-field__type">
        <select className="input" value={role} aria-label="Type" onChange={(e) => setRole(e.target.value)}>
          {Object.entries(roles).map(([id, text]) => <option key={id} value={id}>{text}</option>)}
        </select>
        <input className="input" value={unit} placeholder="Unit (EUR, kg…)" aria-label="Unit"
          onChange={(e) => setUnit(e.target.value)} />
      </div>
      <div className="onto-field__save">
        <Button size="sm" variant="primary" icon={<Check size={14} />} loading={busy} onClick={save}>Save</Button>
        <Button size="sm" variant="ghost" onClick={() => onDone()}>Cancel</Button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ context */
const EXAMPLES = [
  'KUNNR = customer number',
  'Canceled orders are not revenue',
  'Reading should be called Sensor Reading',
]

function ContextBox({ view, onChange }: { view: View; onChange: (next?: View) => void }) {
  const toast = useToast()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [reply, setReply] = useState<{ text: string; changes: number } | null>(null)
  const send = async () => {
    setBusy(true)
    try {
      const out = await api.ontoContext(view.id, text)
      setReply({ text: out.reply, changes: out.changes.length })
      setText('')
      onChange(out.ontology)
    } catch (e) {
      toast.push({ title: 'Note not applied', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  const notes = [...view.notes].reverse().slice(0, 5)
  return (
    <section className="onto-context" aria-label="Add context">
      <h3><MessageSquarePlus size={16} aria-hidden="true" /> Add context</h3>
      <p>Tell it what you know, in your own words. The AI updates the ontology and remembers your note.</p>
      <textarea className="input input--area" rows={4} value={text} aria-label="Context note"
        placeholder="e.g. KUNNR = customer number" onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && text.trim()) void send() }} />
      <div className="onto-context__examples">
        {EXAMPLES.map((x) => <button key={x} type="button" onClick={() => setText(x)}>{x}</button>)}
      </div>
      <Button variant="primary" fullWidth icon={<Send size={14} />} loading={busy}
        disabled={!text.trim()} onClick={send}>Apply</Button>
      {reply ? (
        <Callout tone={reply.changes ? 'success' : 'info'}
          title={reply.changes ? `${reply.changes} change${reply.changes > 1 ? 's' : ''} made` : 'Note saved'}>
          {reply.text}
        </Callout>
      ) : null}
      {notes.length ? (
        <details className="onto-context__notes">
          <summary>Your notes ({view.notes.length})</summary>
          <ul>{notes.map((n) => <li key={n.key}>“{n.text}”</li>)}</ul>
        </details>
      ) : null}
    </section>
  )
}

/* ---------------------------------------------------------------------- ask */
const ASK_EXAMPLES = ['How many records per status?', 'Top 5 by total amount', 'Average per month']

type Cell = string | number | boolean | null

function fmtCell(v: Cell): string {
  if (v === null) return ''
  if (typeof v === 'number') {
    return Number.isInteger(v) ? formatCount(v) : v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  return String(v)
}

function AskPanel({ view }: { view: View }) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<OntoAsk | null>(null)
  const [error, setError] = useState<string | null>(null)
  const send = async (q: string) => {
    if (!q.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.ontoAsk(view.id, q))
    } catch (e) {
      setError(describeError(e).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="onto-ask">
      <section className="onto-ask__box">
        <h3><MessageSquarePlus size={16} aria-hidden="true" /> Ask a question</h3>
        <p>Plain words. The AI writes one read-only query from the published ontology; it is checked, then run. Every number comes from your data.</p>
        <div className="onto-ask__row">
          <input className="input" value={question} placeholder="e.g. how many orders per status?"
            aria-label="Question" onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void send(question) }} />
          <Button variant="primary" icon={<Send size={14} />} loading={busy} disabled={!question.trim()}
            onClick={() => send(question)}>Ask</Button>
        </div>
        {!view.ai.configured ? <p className="onto-ask__warn">No AI model is configured: a question returns the tables and joins to use, not an answer.</p> : null}
        <div className="onto-context__examples">
          {ASK_EXAMPLES.map((x) => <button key={x} type="button" onClick={() => { setQuestion(x); void send(x) }}>{x}</button>)}
        </div>
        {error ? <Callout tone="danger" title="Could not ask">{error}</Callout> : null}
      </section>
      {result ? <AskResult r={result} /> : null}
    </div>
  )
}

function AskResult({ r }: { r: OntoAsk }) {
  const coverage = Math.round(r.coverage * 100)
  return (
    <section className="onto-card onto-ask__result" aria-label="Answer">
      <header className="onto-card__head">
        <div className="onto-card__title"><div>
          <h2>{r.answerable ? r.explanation || 'Answer' : 'Not answered'}</h2>
          <p>{r.note}</p>
        </div></div>
      </header>
      <dl className="onto-facts">
        <div><dt>Things used</dt><dd>{r.things.join(', ') || '—'}</dd></div>
        <div><dt>Question covered</dt><dd>{coverage}%{r.unknown_words.length ? ` (unknown: ${r.unknown_words.join(', ')})` : ''}</dd></div>
        {r.answerable ? <div><dt>Rows</dt><dd>{formatCount(r.row_count)}{r.truncated ? '+' : ''}{r.seconds != null ? ` · ${r.seconds}s` : ''}</dd></div> : null}
        <div><dt>Version</dt><dd>v{r.version}{r.repaired ? ' · query repaired once' : ''}</dd></div>
      </dl>
      {r.answerable && r.columns.length ? (
        <div className="table-scroll onto-ask__table">
          <table className="table table--dense">
            <thead><tr>{r.columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
            <tbody>
              {r.rows.map((row, i) => (
                <tr key={i}>{row.map((v, j) => <td key={j} className={typeof v === 'number' ? 'num' : ''}>{fmtCell(v)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {r.fields_used.length ? (
        <div className="onto-ask__fields">
          <h3>Fields it used</h3>
          <ul>
            {r.fields_used.map((f) => (
              <li key={f.column}>
                <span className={`onto-check onto-check--${f.check}`}>{CHECK[f.check].label}</span>
                <strong>{f.label}</strong>{f.unit ? <span className="onto-pill onto-pill--unit">{f.unit}</span> : null}
                <code>{f.column}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {r.sql ? (
        <details className="onto-ask__sql">
          <summary>The SQL that ran</summary>
          <pre><code>{r.sql}</code></pre>
        </details>
      ) : null}
      {!r.answerable && r.checks.some((c) => !c.passed) ? (
        <ul className="onto-bullets onto-ask__checks">
          {r.checks.filter((c) => !c.passed).map((c) => <li key={c.name}><strong>{c.name}:</strong> {c.detail}</li>)}
        </ul>
      ) : null}
    </section>
  )
}

/* ------------------------------------------------------------------- use it */
function CopyLine({ label, value }: { label: string; value: string }) {
  const toast = useToast()
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      toast.push({ title: 'Copied', message: label, tone: 'success' })
    } catch {
      toast.push({ title: 'Copy it by hand', message: value, tone: 'info' })
    }
  }
  return (
    <div className="onto-copy">
      <span className="onto-copy__label">{label}</span>
      <code className="onto-copy__value" title={value}>{value}</code>
      <button type="button" className="onto-copy__btn" onClick={copy} aria-label={`Copy ${label}`}><Copy size={14} /></button>
    </div>
  )
}

function UseIt({ view }: { view: View }) {
  const use = useAsync((signal) => api.ontoUse(view.id, signal), [view.id, view.version])
  if (!use.data) return <p className="muted">Loading…</p>
  const u = use.data
  return (
    <div className="onto-use">
      <section className="onto-use__card">
        <span className="onto-use__icon"><Table2 size={20} /></span>
        <h3>Nexus and Excel</h3>
        <p>Nexus reads the ontology as three tables: Things, Fields and Links. It always gets the latest version.</p>
        <CopyLine label="Nexus link" value={u.nexus.url} />
        <a className="btn btn--primary btn--md btn--block" href={api.ontoExcelUrl(view.id)} download>
          <Download size={15} /> <span>Download Excel workbook</span>
        </a>
      </section>
      <section className="onto-use__card">
        <span className="onto-use__icon"><MessageSquarePlus size={20} /></span>
        <h3>Claude and other AI agents</h3>
        <p>Agents connect over MCP and call one tool to read the whole ontology in plain words.</p>
        <CopyLine label="MCP address" value={u.agents.mcp_url} />
        <CopyLine label="Tool" value={`${u.agents.tool} {"ontology": "${view.id}"}`} />
        <CopyLine label="Claude Code" value={u.agents.claude_code} />
        <p className="onto-use__note">An agent needs a key. <Link to="/agents">Create one on the Agents page</Link>.</p>
      </section>
      <section className="onto-use__card">
        <span className="onto-use__icon"><FileJson size={20} /></span>
        <h3>Files</h3>
        <p>Standard formats for other tools and for your Git repository.</p>
        <ul className="onto-use__files">
          <li><a href={u.files.json} target="_blank" rel="noreferrer"><FileJson size={15} /> JSON</a><span>Same tables as Nexus</span></li>
          <li><a href={u.files.ossie}><FileJson size={15} /> Apache Ossie</a><span>Semantic-layer interchange (NVIDIA, Snowflake…)</span></li>
          <li><a href={u.files.owl} target="_blank" rel="noreferrer"><Share2 size={15} /> OWL / Turtle</a><span>Standard ontology format</span></li>
          <li><a href={u.files.shacl} target="_blank" rel="noreferrer"><CircleCheck size={15} /> SHACL</a><span>Data quality rules</span></li>
          <li><a href={u.files.git_zip}><GitBranch size={15} /> Git folder</a><span>Ontology as code (.zip)</span></li>
        </ul>
      </section>
    </div>
  )
}
