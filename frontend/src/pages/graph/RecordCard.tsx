import { Lock } from 'lucide-react'
import type { KgEntity, KgRef } from '../../api/types'
import { ThingIcon } from '../../components/ThingIcon'
import { ProofMark } from '../../components/ProofMark'

/**
 * One real record, read like a sentence (plan step 2.1). The default
 * Knowledge-graph view: a readable name, a one-line summary built from the
 * record's own values, and its links grouped by what they mean ("has 4 order
 * lines", "belongs to Customer 12"). The dot picture is one click away, not
 * the first thing a business user meets.
 */
export function RecordCard({
  entity,
  icon,
  onOpen,
  actions,
}: {
  entity: KgEntity
  icon?: string
  onOpen: (ref: KgRef) => void
  actions?: React.ReactNode
}) {
  const out = entity.connections.filter((c) => c.direction === 'out')
  const incoming = entity.connections.filter((c) => c.direction === 'in')
  return (
    <article className="reccard">
      <div className="reccard__head">
        <ThingIcon icon={icon ?? entity.icon} tint size={22} />
        <div className="reccard__title">
          <span className="reccard__name">{entity.label ?? entity.key}</span>
          <span className="reccard__kind">{entity.thing}</span>
        </div>
      </div>

      {entity.summary ? <p className="reccard__summary">{entity.summary}</p> : null}

      <div className="reccard__links">
        {incoming.map((c) => (
          <div key={`in:${c.link}`} className="reccard__verb">
            <span className="reccard__verb-label">
              has <b>{c.count.toLocaleString('en-US')}</b> {c.thing ?? 'linked records'}
            </span>
            <ProofMark kind="proved" size="sm" />
            <div className="reccard__chips">
              {c.items.slice(0, 5).map((it) => (
                <button key={`${it.set}|${it.key}`} type="button" className="reccard__chip"
                  onClick={() => onOpen(it)}>
                  {it.label ?? it.key}
                </button>
              ))}
              {c.count > c.items.slice(0, 5).length
                ? <span className="reccard__more">+{(c.count - Math.min(5, c.items.length)).toLocaleString('en-US')} more</span>
                : null}
            </div>
          </div>
        ))}

        {out.map((c) => (
          <div key={`out:${c.link}`} className="reccard__verb">
            <span className="reccard__verb-label">{c.text}</span>
            {c.broken
              ? <ProofMark kind="disagrees" size="sm" label="not found" />
              : <ProofMark kind="proved" size="sm" />}
            <div className="reccard__chips">
              {c.broken
                ? <span className="reccard__chip is-broken">{c.thing} {c.value} — not in the data</span>
                : c.items.map((it) => (
                  <button key={`${it.set}|${it.key}`} type="button" className="reccard__chip"
                    onClick={() => onOpen(it)}>
                    {it.label ?? it.key}
                  </button>
                ))}
            </div>
          </div>
        ))}
      </div>

      <details className="reccard__verb" style={{ borderTop: '1px solid var(--border)' }}>
        <summary className="reccard__verb-label" style={{ cursor: 'pointer' }}>Show all fields</summary>
        <dl className="kgp__fields" style={{ marginTop: 10 }}>
          {entity.fields.map((f) => (
            <div key={f.column}>
              <dt>{f.label}</dt>
              <dd>
                {f.value === null || f.value === '' ? <span className="kg-muted">empty</span> : String(f.value)}
                {f.personal ? <Lock size={11} aria-label="Personal data, masked" /> : null}
              </dd>
            </div>
          ))}
        </dl>
      </details>

      {actions ? <div className="reccard__foot">{actions}</div> : null}
    </article>
  )
}
