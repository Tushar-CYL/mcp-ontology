import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CircleCheck, CircleDashed, Cpu, RefreshCw, ShieldCheck, TriangleAlert, Users } from 'lucide-react'
import { api } from '../api/client'
import type { LayerTrust, TrustLayer } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { cx } from '../utils/cx'

const WHERE: Record<string, { label: string; path?: (oid: string) => string }> = {
  review: { label: 'Ontology review', path: (oid) => `/tools/ontology/${encodeURIComponent(oid)}` },
  notes: { label: 'Add context on the Ontology page', path: (oid) => `/tools/ontology/${encodeURIComponent(oid)}` },
  rules: { label: 'Business rules on the Ontology page', path: (oid) => `/tools/ontology/${encodeURIComponent(oid)}?tab=rules` },
  graph: { label: 'Knowledge graph' },
  semantic: { label: 'Semantic page', path: (oid) => `/tools/semantic/${encodeURIComponent(oid)}` },
  report_check: { label: 'Report check on the Context page', path: (oid) => `/tools/context/${encodeURIComponent(oid)}` },
  gaps: { label: 'Unanswered questions on the Context page', path: (oid) => `/tools/context/${encodeURIComponent(oid)}` },
}

const TITLE: Record<TrustLayer, string> = {
  ontology: 'Why you can trust this ontology',
  graph: 'Why you can trust this knowledge graph',
  semantic: 'Why you can trust these numbers',
  context: 'Why you can trust these answers',
}

const when = (at?: string | null) => (at ? new Date(at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '')

/**
 * Two sides of trust, side by side: what the data proved (how the layer was
 * built and checked) and what the business's own people added (rules,
 * definitions, approvals, owners, trusted reports), with what is still missing.
 */
const SUMMARY: Record<TrustLayer, string> = {
  ontology: 'How this ontology was checked',
  graph: 'How this knowledge graph was checked',
  semantic: 'How these numbers were checked',
  context: 'How these answers were checked',
}

/**
 * The two sides of trust. By default it is a quiet, collapsed "How this was
 * checked" strip (closed), so the page leads with the real content and the
 * proof is one click away - the pattern the market uses. Pass
 * `collapsible={false}` to show it open as a full card.
 */
export function TrustPanel({ oid, layer, here, collapsible = true }: {
  oid: string; layer: TrustLayer; here?: string[]; collapsible?: boolean
}) {
  const [open, setOpen] = useState(!collapsible)
  const t = useAsync<LayerTrust>((signal) => api.layerTrust(oid, layer, signal), [oid, layer],
    { enabled: open })
  const d = t.data
  const body = (
    <>
      {!d ? (
        <p className="trust__muted">{t.error ? 'Could not read the checks just now.' : 'Reading the checks…'}</p>
      ) : (
        <div className="trust__sides">
          <div className="trust__side">
            <p className="trust__kicker"><Cpu size={15} aria-hidden="true" /> Technical proof: how it was built and checked</p>
            <p className="trust__headline">{d.proof.headline}</p>
            <ol className="trust__steps">
              {d.proof.steps.map((s) => (
                <li key={s.title} className={`is-${s.status}`}>
                  {s.status === 'ok' ? <CircleCheck size={18} aria-label="Checked" />
                    : s.status === 'warn' ? <TriangleAlert size={18} aria-label="Problem found" />
                      : <CircleDashed size={18} aria-label="Not checked yet" />}
                  <div><strong>{s.title}</strong><span>{s.text}</span></div>
                </li>
              ))}
            </ol>
          </div>

          <div className="trust__side">
            <p className="trust__kicker"><Users size={15} aria-hidden="true" /> Business knowledge: what your people added</p>
            <p className="trust__headline">{d.people.headline}</p>
            <div className="trust__counts">
              {d.people.counts.map((c) => (
                <div key={c.label} className={cx('trust__count', !c.value && 'is-zero')}>
                  <b>{c.value.toLocaleString()}</b><span>{c.label}</span>
                </div>
              ))}
            </div>
            {d.people.recent.length ? (
              <ul className="trust__recent" aria-label="Latest from your people">
                {d.people.recent.map((r, i) => (
                  <li key={`${r.at}-${i}`}><span>{r.text}</span>
                    <small>{[r.by, when(r.at)].filter(Boolean).join(' · ')}</small></li>
                ))}
              </ul>
            ) : null}
            {d.people.missing.length ? (
              <div className="trust__missing">
                <p className="trust__kicker">Still missing from your people</p>
                <ul>
                  {d.people.missing.map((m) => {
                    const w = WHERE[m.where]
                    const local = here?.includes(m.where)
                    return (
                      <li key={m.text}>
                        <span>{m.text}</span>
                        {w ? (w.path && !local
                          ? <Link to={w.path(oid)}>{w.label} →</Link>
                          : <small>{local ? 'On this page' : w.label}</small>) : null}
                      </li>
                    )
                  })}
                </ul>
              </div>
            ) : <p className="trust__muted">Nothing missing: your people have covered what the data could not.</p>}
          </div>
        </div>
      )}
    </>
  )

  if (!collapsible) {
    return (
      <section className="trust" aria-label={TITLE[layer]}>
        <div className="trust__head">
          <h2>{TITLE[layer]}</h2>
          <button type="button" className="trust__refresh" onClick={t.reload} aria-label="Refresh" title="Refresh">
            <RefreshCw size={14} aria-hidden="true" className={cx(t.loading && 'is-spinning')} />
          </button>
        </div>
        {body}
      </section>
    )
  }

  return (
    <details className="trust-disclose" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary><ShieldCheck size={15} aria-hidden="true" /> {SUMMARY[layer]}</summary>
      <section className="trust trust--embedded" aria-label={TITLE[layer]}>{body}</section>
    </details>
  )
}
