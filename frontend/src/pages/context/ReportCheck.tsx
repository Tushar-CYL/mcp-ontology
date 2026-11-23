import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleCheck, ClipboardList, Lightbulb, Play, Trash2, TriangleAlert, Upload } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { CheckVerdict, CtxGaps, CtxInsights, ReportCheckOverview, ReportCheckResult } from '../../api/types'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { cx } from '../../utils/cx'
import { JobLog } from '../ontology/shared'
import { type CheckSuggestion, suggestChecks, templateCsv } from './checkSuggestions'

const GOOD: CheckVerdict[] = ['pass', 'refused_ok']

function fmt(n: number | null | undefined): string {
  if (n == null) return '—'
  return Math.abs(n) >= 1000 || Number.isInteger(n) ? n.toLocaleString('en-US', { maximumFractionDigits: 2 })
    : n.toLocaleString('en-US', { maximumSignificantDigits: 6 })
}

function pct(n: number | null | undefined): string {
  return n == null ? '—' : `${n}%`
}

/** Report check: numbers from the client's own reports, asked of Strata and
 *  scored the way Databricks and Snowflake score their own tools. */
export function ReportCheck({ oid, insights }: { oid: string; insights?: CtxInsights }) {
  const toast = useToast()
  const state = useAsync<ReportCheckOverview>((signal) => api.ctxChecks(oid, signal), [oid])
  const gaps = useAsync<CtxGaps>((signal) => api.ctxGaps(oid, signal), [oid])
  const number = useRef<HTMLInputElement>(null)
  // After a suggestion is picked and the form has drawn, the cursor goes to the number.
  const [focusNumber, setFocusNumber] = useState(0)
  useEffect(() => {
    if (focusNumber) number.current?.focus()
  }, [focusNumber])
  const [data, setData] = useState<ReportCheckOverview | null>(null)
  const view = data ?? state.data
  const [jobId, setJobId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ question: '', expected: '', row: '', unit: '', phrasings: '', source: '', refuse: false })
  const [busy, setBusy] = useState(false)
  const file = useRef<HTMLInputElement>(null)

  const save = async (body: Parameters<typeof api.ctxChecksAdd>[1], said: string) => {
    setBusy(true)
    try {
      setData(await api.ctxChecksAdd(oid, body))
      toast.push({ title: said, tone: 'success' })
      return true
    } catch (e) {
      toast.push({ title: 'Could not add the check', message: describeError(e).message, tone: 'error' })
      return false
    } finally {
      setBusy(false)
    }
  }
  const addOne = async () => {
    const ok = await save({ checks: [{
      question: form.question.trim(), expected: form.refuse ? null : form.expected.trim(),
      row_label: form.row.trim() || null, unit: form.unit.trim() || null, refuse: form.refuse,
      phrasings: form.phrasings.split('|').map((x) => x.trim()).filter(Boolean).slice(0, 4),
      source: form.source.trim() || null,
    }] }, 'Check added')
    if (ok) setForm({ question: '', expected: '', row: '', unit: '', phrasings: '', source: '', refuse: false })
  }
  const upload = async (f: File) => {
    const excel = /\.xlsx?m?$/i.test(f.name)
    let content: string
    if (excel) {
      const bytes = new Uint8Array(await f.arrayBuffer())
      let bin = ''
      for (let i = 0; i < bytes.length; i += 1) bin += String.fromCharCode(bytes[i])
      content = btoa(bin)
    } else {
      content = await f.text()
    }
    await save({ file_name: f.name, file_content: content }, `Checks added from ${f.name}`)
  }
  const remove = async (id: string) => {
    try {
      setData(await api.ctxChecksRemove(oid, id))
    } catch (e) {
      toast.push({ title: 'Could not remove it', message: describeError(e).message, tone: 'error' })
    }
  }
  const run = async () => {
    try {
      setJobId((await api.ctxChecksRun(oid)).job_id)
    } catch (e) {
      toast.push({ title: 'Could not start the check', message: describeError(e).message, tone: 'error' })
    }
  }

  const suggestions = useMemo(() => suggestChecks(insights, gaps.data, (view?.checks ?? []).map((c) => c.question)),
    [insights, gaps.data, view?.checks])
  const pick = (sg: CheckSuggestion) => {
    setAdding(true)
    setForm({ question: sg.question, expected: '', row: sg.row ?? '', unit: '', phrasings: '', source: '',
      refuse: Boolean(sg.refuse) })
    // The number is the person's to type, from their report.
    if (!sg.refuse) setFocusNumber((n) => n + 1)
  }

  const last = view?.last_run
  const s = last?.summary
  const checks = view?.checks ?? []

  return (
    <Card className="rc" title={<><ClipboardList size={18} aria-hidden="true" /> Report check</>}
      subtitle="Does Strata give the numbers your own reports give? Add numbers from 3–5 real reports; Strata answers each from the data and we compare, to the report's precision."
      actions={<>
        <Button size="sm" variant="ghost" icon={<Upload size={14} />} disabled={busy}
          onClick={() => file.current?.click()}>Add from CSV or Excel</Button>
        <Button size="sm" variant="primary" icon={<Play size={14} />} disabled={!checks.length || Boolean(jobId)}
          onClick={run}>Run the check</Button>
      </>}>
      <input ref={file} type="file" accept=".csv,.xlsx,.xlsm" hidden
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) void upload(f) }} />

      {jobId ? (
        <JobLog jobId={jobId} onFinished={(job) => {
          setJobId(null)
          setData(null)
          state.reload()
          toast.push({ title: job.status === 'done' ? 'Report check finished' : 'Report check failed',
            message: job.error ?? undefined, tone: job.status === 'done' ? 'success' : 'error' })
        }} />
      ) : null}

      <details className="rc__how" open={!checks.length}>
        <summary>How to use it</summary>
        <ol>
          <li><strong>Pick 3–5 reports you already trust</strong>: a sales pack, a finance summary, a dashboard people use.</li>
          <li><strong>For each number in them, add a check</strong>: the question people ask, and the number <em>exactly as the
            report shows it</em> (1,466,849 or 1.5M; a rounded number is compared at the precision it is written with).
            If the report lists rows (by country, by Incoterms, by month), say which row.</li>
          <li><strong>Add one or two questions Strata should refuse</strong>: something your data does not hold. A good
            assistant says it cannot answer; it does not guess.</li>
          <li><strong>Run the check.</strong> Green means Strata matches the report. Red marked <em>silent</em> means a wrong
            number shown as an answer: fix those first (the Ontology review, a note, or a certified metric).</li>
        </ol>
        <p className="rc__muted">Type the number from the report, never Strata&apos;s own: the test compares Strata with your
          report, not with itself. Checks are never shown to the AI as hints.</p>
      </details>

      {suggestions.length ? (
        <div className="rc__suggest">
          <span className="rc__suggest-head"><Lightbulb size={14} aria-hidden="true" /> Suggested from your data: click one, then type the number your report shows</span>
          <div className="rc__chips">
            {suggestions.map((sg) => (
              <button key={`${sg.question}|${sg.row ?? ''}`} type="button" className={cx('rc-chip', sg.refuse && 'is-refuse')}
                title={sg.why} onClick={() => pick(sg)}>
                <span>{sg.question}</span>
                {sg.row ? <small>row {sg.row}</small> : null}
                {sg.refuse ? <small>should refuse</small> : null}
              </button>
            ))}
          </div>
          <a className="rc__template" download="report-check.csv"
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(templateCsv(suggestions))}`}>
            Download these as a CSV to fill in from your report</a>
        </div>
      ) : null}

      {s ? (
        <>
          <div className="rc__score" aria-label="Scorecard">
            <Score big value={pct(s.accuracy_pct)} label="Numbers that match the reports" />
            <Score value={pct(s.certified.pct)} label={`From certified metrics (${s.certified.asked} asked)`} />
            <Score value={pct(s.other.pct)} label={`From other answers (${s.other.asked} asked)`} />
            <Score value={pct(s.refusals.pct)} label={`Refused when it should (${s.refusals.asked} asked)`} />
            <Score value={pct(s.agreement_pct)} label="Same answer for every phrasing" />
            <Score value={String(s.silent_wrong)} label="Silent wrong numbers (must be 0)"
              tone={s.silent_wrong ? 'bad' : 'good'} />
          </div>
          <p className="rc__muted">
            Last run {new Date(last!.at).toLocaleString()} · {s.passed} of {s.checks} checks fully match · {s.asked} questions asked
            {s.seconds != null ? ` in ${s.seconds}s` : ''}. A number is a match when it equals the report to the report's precision (4 significant digits unless you set it).
          </p>
          <Results results={last!.results} />
        </>
      ) : checks.length ? (
        <p className="rc__muted">{checks.length} check{checks.length === 1 ? '' : 's'} ready. Run the check to see the scorecard.</p>
      ) : null}

      <details className="rc__checks" open={adding || (!s && checks.length > 0 && checks.length < 6)}>
        <summary>Your checks ({checks.length})</summary>
        <ul>
          {checks.map((c) => (
            <li key={c.id}>
              <span className="rc__q">{c.question}{c.phrasings.length ? <small> +{c.phrasings.length} other phrasing{c.phrasings.length === 1 ? '' : 's'}</small> : null}</span>
              <span className="rc__exp">{c.refuse ? 'should refuse' : `${fmt(c.expected)}${c.unit ? ` ${c.unit}` : ''}${c.row_label ? ` (row ${c.row_label})` : ''}`}</span>
              <span className="rc__src">{c.source ?? ''}</span>
              <button type="button" aria-label={`Remove ${c.question}`} onClick={() => void remove(c.id)}><Trash2 size={14} /></button>
            </li>
          ))}
        </ul>
        {adding ? (
          <form className="rc__form" onSubmit={(e) => { e.preventDefault(); void addOne() }}>
            <label className="rc__wide">Question people ask
              <input className="input" required maxLength={1000} value={form.question}
                onChange={(e) => setForm({ ...form, question: e.target.value })} /></label>
            <label>Number in the report
              <input ref={number} className="input" disabled={form.refuse} required={!form.refuse} value={form.expected}
                placeholder="1,466,849 or 1.5M" onChange={(e) => setForm({ ...form, expected: e.target.value })} />
              <small>Exactly as the report shows it.</small></label>
            <label>Row (when the answer is a list)
              <input className="input" value={form.row} placeholder="DDP, DE, 2020-03"
                onChange={(e) => setForm({ ...form, row: e.target.value })} />
              <small>Which line of the report table.</small></label>
            <label>Unit
              <input className="input" value={form.unit} placeholder="orders, EUR"
                onChange={(e) => setForm({ ...form, unit: e.target.value })} /></label>
            <label className="rc__wide">Other ways people ask it (separate with |)
              <input className="input" value={form.phrasings} placeholder="Optional: proves the wording does not change the answer"
                onChange={(e) => setForm({ ...form, phrasings: e.target.value })} /></label>
            <label className="rc__wide">Which report (page)
              <input className="input" value={form.source} placeholder="So anyone can find the number again"
                onChange={(e) => setForm({ ...form, source: e.target.value })} /></label>
            <label className="rc__check"><input type="checkbox" checked={form.refuse}
              onChange={(e) => setForm({ ...form, refuse: e.target.checked })} /> Strata should refuse this question</label>
            <div className="rc__actions">
              <Button type="submit" size="sm" variant="primary" loading={busy}>Add check</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setAdding(false)}>Done</Button>
            </div>
          </form>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>Add a check</Button>
        )}
      </details>
    </Card>
  )
}

function Score({ value, label, big, tone }: { value: string; label: string; big?: boolean; tone?: 'good' | 'bad' }) {
  return (
    <div className={cx('rc-score', big && 'is-big', tone && `is-${tone}`)}>
      <span className="rc-score__value">{value}</span>
      <span className="rc-score__label">{label}</span>
    </div>
  )
}

function Results({ results }: { results: ReportCheckResult[] }) {
  return (
    <div className="rc__table" role="table" aria-label="Every check">
      <div className="rc__row rc__row--head" role="row">
        <span role="columnheader">Question</span><span role="columnheader">Report says</span>
        <span role="columnheader">Strata got</span><span role="columnheader">Verdict</span>
      </div>
      {results.map((r) => (
        <div key={r.id} className={cx('rc__row', !r.passed && 'is-fail')} role="row">
          <span role="cell">{r.question}{r.source ? <small>{r.source}</small> : null}</span>
          <span role="cell">{r.refuse ? 'refuse' : `${fmt(r.expected)}${r.unit ? ` ${r.unit}` : ''}`}{r.row_label ? <small>row {r.row_label}</small> : null}</span>
          <span role="cell">{fmt(r.answers[0]?.got)}<small>{r.answers[0]?.certified ? `certified: ${r.answers[0].metric}` : r.answers[0]?.how}</small></span>
          <span role="cell" className="rc__verdicts">
            {r.answers.map((a, i) => (
              <span key={i} className={cx('rc-verdict', GOOD.includes(a.verdict) ? 'is-good' : 'is-bad')}
                title={`${a.phrasing}: ${a.label}${a.got != null ? ` (${fmt(a.got)})` : ''}`}>
                {GOOD.includes(a.verdict) ? <CircleCheck size={12} aria-hidden="true" /> : <TriangleAlert size={12} aria-hidden="true" />}
                {a.label}{a.silent ? ' · silent' : ''}
              </span>
            ))}
          </span>
        </div>
      ))}
    </div>
  )
}
