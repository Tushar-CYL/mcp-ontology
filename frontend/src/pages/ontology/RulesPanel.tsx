import { useState } from 'react'
import { CircleCheck, Lightbulb, Play, RefreshCw, ShieldCheck, Trash2, TriangleAlert } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { BizRule, RulesListing } from '../../api/types'
import { Button } from '../../components/Button'
import { useToast } from '../../context/ToastContext'
import { WhatDepends } from '../../components/WhatDepends'
import { useAsync } from '../../hooks/useAsync'
import { cx } from '../../utils/cx'

const TYPE: Record<string, string> = {
  required: 'Must have a value', range: 'Number limits', allowed: 'Allowed values',
  unique: 'No duplicates', exists: 'Must point to a real record', excluded: 'Does not count',
}
const STATUS: Record<string, string> = { proposed: 'Proposed', active: 'Active', retired: 'Retired' }

/**
 * Business rules you can check. A person writes a rule in plain words (or
 * picks one suggested from the data); Strata turns it into a check, runs it
 * on the data and shows who follows it and who does not. A person activates
 * it with an owner: only then does the AI get it as a fact.
 */
export function RulesPanel({ oid }: { oid: string }) {
  const toast = useToast()
  const state = useAsync<RulesListing>((signal) => api.rules(oid, signal), [oid])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const d = state.data

  const act = async (key: string, fn: () => Promise<unknown>, done: string) => {
    setBusy(key)
    try {
      await fn()
      toast.push({ title: done, tone: 'success' })
      state.reload()
    } catch (e) {
      toast.push({ title: 'Not done', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(null)
    }
  }
  const add = (words: string) => act('add', () => api.ruleAdd(oid, words).then(() => setText('')),
    'Rule checked on the data')

  return (
    <section className="rules" aria-label="Business rules">
      <div className="rules__intro">
        <h2>Business rules</h2>
        <p>Write a rule the way your business says it. Strata turns it into a check, runs it on the data
          and shows which records break it. Nothing changes until a person activates it; then every answer
          the AI gives about that thing comes with the rule.</p>
      </div>

      <form className="rules__write" onSubmit={(e) => { e.preventDefault(); if (text.trim()) void add(text.trim()) }}>
        <input className="input" value={text} maxLength={500} aria-label="A business rule in plain words"
          placeholder={d?.suggestions[0] ? `For example: ${d.suggestions[0].text}` : 'A rule in plain words'}
          onChange={(e) => setText(e.target.value)} />
        <Button type="submit" variant="primary" icon={<Play size={14} />} loading={busy === 'add'}
          disabled={!text.trim()}>Check it on the data</Button>
      </form>

      {d?.suggestions.length ? (
        <div className="rules__suggest">
          <p className="rules__kicker"><Lightbulb size={14} aria-hidden="true" /> Suggested from your data: click one to check it</p>
          <div className="rules__chips">
            {d.suggestions.map((s) => (
              <button key={s.text} type="button" className={cx('rules-chip', s.broken > 0 && 'is-broken')}
                disabled={busy === 'add'} title={s.why} onClick={() => void add(s.text)}>
                <span>{s.text}</span><small>{s.why}</small>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {d?.conflicts.length ? (
        <div className="rules__conflicts" role="alert">
          <p className="rules__kicker"><TriangleAlert size={14} aria-hidden="true" /> Metrics that ignore a rule</p>
          <ul>
            {d.conflicts.map((c) => (
              <li key={`${c.rule}|${c.metric}`}>{c.text}{c.certified ? ' (certified)' : ''}. Fix the metric&apos;s
                filter on the Semantic page, or retire the rule.</li>
            ))}
          </ul>
        </div>
      ) : null}

      {!d ? <p className="rules__muted">{state.error ? describeError(state.error).message : 'Reading the rules…'}</p> : (
        <>
          <p className="rules__summary">{d.summary.active} active · {d.summary.proposed} waiting for a decision
            {d.summary.failing ? ` · ${d.summary.failing} broken by some records` : ''}</p>
          {d.rules.length ? (
            <ul className="rules__list">
              {d.rules.map((r) => <RuleCard key={r.id} oid={oid} r={r} busy={busy} act={act} />)}
            </ul>
          ) : <p className="rules__muted">No rules yet. Write one, or click a suggestion above.</p>}
        </>
      )}
    </section>
  )
}

function RuleCard({ oid, r, busy, act }: {
  oid: string
  r: BizRule
  busy: string | null
  act: (key: string, fn: () => Promise<unknown>, done: string) => Promise<void>
}) {
  const [owner, setOwner] = useState(r.owner ?? '')
  const res = r.result
  const counting = r.spec.type === 'excluded'
  const failed = res.failed ?? 0
  const pct = counting ? null : res.passed_pct ?? null
  return (
    <li className={cx('rule', `is-${r.status}`, !counting && failed > 0 && 'is-broken')}>
      <div className="rule__head">
        <span className={cx('rule__status', `is-${r.status}`)}>{STATUS[r.status]}</span>
        <span className="rule__type">{TYPE[r.spec.type] ?? r.spec.type} · {r.spec.thing} . {r.spec.label}</span>
      </div>
      <p className="rule__text">{r.text}</p>

      {res.error ? <p className="rule__error"><TriangleAlert size={14} aria-hidden="true" /> {res.error}</p> : counting ? (
        <p className="rule__result">Leaves out <strong>{(res.affected ?? 0).toLocaleString()}</strong> of {(res.checked ?? 0).toLocaleString()} records
          ({res.share_pct}%) whose {r.spec.label} is {(r.spec.values ?? []).join(', ')}.</p>
      ) : (
        <div className="rule__result">
          <div className="rule__bar" aria-hidden="true"><i style={{ width: `${pct ?? 0}%` }} /></div>
          <p>{failed ? <TriangleAlert size={14} aria-hidden="true" /> : <CircleCheck size={14} aria-hidden="true" />}{' '}
            <strong>{((res.checked ?? 0) - failed).toLocaleString()}</strong> of {(res.checked ?? 0).toLocaleString()} records follow it
            {failed ? <> · <strong className="rule__bad">{failed.toLocaleString()} break it</strong></> : null}</p>
        </div>
      )}
      {res.examples?.length && (failed || counting) ? (
        <ul className="rule__examples" aria-label="Examples from the data">
          {res.examples.map((x, i) => (
            <li key={i}><code>{x.record ?? '–'}</code> {r.spec.label}: <code>{x.value ?? 'empty'}</code></li>
          ))}
        </ul>
      ) : null}

      <p className="rule__meta">Written by {r.by}{r.owner ? ` · owner ${r.owner}` : ''}
        {r.decided_by ? ` · ${r.status === 'active' ? 'activated' : 'decided'} by ${r.decided_by}` : ''}
        {res.at ? ` · checked ${new Date(res.at).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}` : ''}</p>

      <div className="rule__actions">
        {r.status !== 'active' ? (
          <>
            <input className="input" value={owner} placeholder="Owner, e.g. a team" aria-label="Owner"
              onChange={(e) => setOwner(e.target.value)} />
            <Button size="sm" variant="primary" icon={<ShieldCheck size={14} />} loading={busy === `on:${r.id}`}
              onClick={() => void act(`on:${r.id}`, () => api.ruleActivate(oid, r.id, owner), 'Rule active: the AI now uses it')}>
              Activate</Button>
          </>
        ) : (
          <Button size="sm" variant="secondary" loading={busy === `off:${r.id}`}
            onClick={() => void act(`off:${r.id}`, () => api.ruleRetire(oid, r.id), 'Rule retired')}>Retire</Button>
        )}
        <Button size="sm" variant="ghost" icon={<RefreshCw size={14} />} loading={busy === `chk:${r.id}`}
          onClick={() => void act(`chk:${r.id}`, () => api.ruleCheck(oid, r.id), 'Checked again')}>Check again</Button>
        <Button size="sm" variant="ghost" icon={<Trash2 size={14} />} loading={busy === `rm:${r.id}`}
          onClick={() => void act(`rm:${r.id}`, () => api.ruleRemove(oid, r.id), 'Rule removed')}>Remove</Button>
      </div>
      <WhatDepends oid={oid} kind="rule" target={r.id} compact />
    </li>
  )
}
