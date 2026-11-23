import { useState } from 'react'
import { Check, CircleCheck, Search, Undo2, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { OntoReviewCard, OntoReviewQueue, OntoView as View } from '../../api/types'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { CHECK, formatCount } from '../../utils/onto'

/** Review by exception: only the claims the data could not settle, most
 *  important first, with what the data shows before what the AI said. */
export function ReviewPanel({ view, onChange, onClose }: {
  view: View
  onChange: (next?: View) => void
  onClose: () => void
}) {
  const toast = useToast()
  const { data, loading, error, reload } = useAsync<OntoReviewQueue>(
    (signal) => api.ontoReview(view.id, signal), [view.id])
  const [busy, setBusy] = useState<string | null>(null)

  const act = async (key: string, run: () => Promise<{ ontology: View }>, said: string) => {
    setBusy(key)
    try {
      const out = await run()
      onChange(out.ontology)
      reload()
      toast.push({ title: said, tone: 'success' })
    } catch (e) {
      toast.push({ title: 'Could not save that', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(null)
    }
  }
  const decide = (card: OntoReviewCard, decision: 'approved' | 'rejected') =>
    act(card.target, () => api.ontoReviewDecide(view.id, { targets: [card.target], decision }),
      decision === 'approved' ? `Approved: ${card.title}` : `Rejected: ${card.title}. No layer uses it now.`)
  const approveThing = (thing: string, n: number) =>
    act(`thing:${thing}`, () => api.ontoReviewDecide(view.id, { decision: 'approved', thing }),
      `Approved ${n} in ${thing}`)
  const undo = (target: string, title: string) =>
    act(target, () => api.ontoReviewUndo(view.id, target), `Taken back: ${title}`)

  const counts = data?.counts ?? view.summary.review
  const cards = data?.cards ?? []
  const unproven = cards.filter((c) => c.why === 'unproven')
  const spots = cards.filter((c) => c.why === 'spot_check')
  const perThing = unproven.reduce<Record<string, number>>((acc, c) => {
    acc[c.thing] = (acc[c.thing] ?? 0) + 1
    return acc
  }, {})
  const stats = data?.stats

  return (
    <Card className="review" title="Review: only what the data could not settle"
      subtitle="The data already proved the rest. Look at the evidence, then decide."
      actions={<Button size="sm" variant="ghost" icon={<X size={14} />} onClick={onClose}>Close</Button>}>
      {counts ? (
        <ul className="review__counts" aria-label="Where every claim stands">
          <li className="is-you"><strong>{formatCount(counts.needs_you)}</strong> need you</li>
          {counts.spot_checks ? <li className="is-you"><strong>{formatCount(counts.spot_checks)}</strong> spot check{counts.spot_checks === 1 ? '' : 's'}</li> : null}
          <li className="is-ok"><strong>{formatCount(counts.confirmed)}</strong> confirmed by checks</li>
          <li className="is-bad"><strong>{formatCount(counts.disagrees)}</strong> data disagrees (held back already)</li>
          <li><strong>{formatCount(counts.approved + counts.set_by_you)}</strong> decided or written by people</li>
          {counts.rejected ? <li><strong>{formatCount(counts.rejected)}</strong> rejected</li> : null}
        </ul>
      ) : null}

      {loading && !data ? <p className="review__muted">Loading the queue…</p> : null}
      {error ? <p className="review__muted">Could not load the queue: {describeError(error).message}</p> : null}

      {data && !cards.length ? (
        <p className="review__done"><CircleCheck size={16} aria-hidden="true" /> Nothing needs you. The data settled every claim, or a person already decided.</p>
      ) : null}

      {unproven.length ? (
        <section className="review__group" aria-label="Needs you">
          <div className="review__group-head">
            <h3>Needs you <span>{unproven.length}</span></h3>
            <p>Nothing in the data can prove or disprove these. Most important first.</p>
            <div className="review__bulk">
              {Object.entries(perThing).filter(([, n]) => n > 1).map(([thing, n]) => (
                <Button key={thing} size="sm" variant="secondary" icon={<Check size={14} />}
                  disabled={Boolean(busy)} onClick={() => approveThing(thing, n)}>
                  Approve all {n} in {thing}
                </Button>
              ))}
            </div>
          </div>
          {unproven.map((c) => <ReviewCard key={c.target} card={c} busy={busy === c.target} onDecide={decide} />)}
        </section>
      ) : null}

      {spots.length ? (
        <section className="review__group" aria-label="Spot checks">
          <div className="review__group-head">
            <h3><Search size={15} aria-hidden="true" /> Spot checks <span>{spots.length}</span></h3>
            <p>The data confirmed these. A small steady sample is shown to a person, so we know how often the checks themselves are wrong.</p>
          </div>
          {spots.map((c) => <ReviewCard key={c.target} card={c} busy={busy === c.target} onDecide={decide} />)}
        </section>
      ) : null}

      {data?.rejected_links.length ? (
        <section className="review__group" aria-label="Rejected links">
          <div className="review__group-head"><h3>Links you rejected <span>{data.rejected_links.length}</span></h3>
            <p>No layer joins records through these.</p></div>
          {data.rejected_links.map((l) => (
            <div key={l.key} className="review__rejected">
              <span>{l.label}</span>
              <Button size="sm" variant="ghost" icon={<Undo2 size={14} />} disabled={Boolean(busy)}
                onClick={() => undo(`link:${l.key}`, l.label)}>Take back</Button>
            </div>
          ))}
        </section>
      ) : null}

      {stats && stats.decisions ? (
        <p className="review__stats">
          So far: {stats.decisions} decision{stats.decisions === 1 ? '' : 's'}, {stats.acceptance_pct}% accepted
          {stats.spot_checked ? `; spot checks found a data check wrong ${stats.checks_wrong_pct}% of the time (${stats.spot_checked} checked)` : ''}.
          These are Strata's own numbers, measured here.
        </p>
      ) : null}
    </Card>
  )
}

function ReviewCard({ card, busy, onDecide }: {
  card: OntoReviewCard
  busy: boolean
  onDecide: (card: OntoReviewCard, decision: 'approved' | 'rejected') => void
}) {
  const check = CHECK[card.evidence.check]
  return (
    <article className="review-card">
      <header className="review-card__head">
        <strong>{card.title}</strong>
        <code>{card.column}</code>
        <span className={`review-card__why is-${card.why}`}>
          {card.why === 'spot_check' ? 'Spot check' : "Can't be proven from the data"}
        </span>
      </header>
      <div className="review-card__body">
        <div className="review-card__evidence">
          <span className="review-card__label">What the data shows</span>
          <span className={`onto-check onto-check--${card.evidence.check}`}>{check.label}</span>
          <span>{card.evidence.proof || 'No proof either way.'}</span>
          {card.evidence.records ? <span className="review__muted">{formatCount(card.evidence.records)} records</span> : null}
          {card.evidence.match != null ? <span className="review__muted">{Math.round(card.evidence.match * 100)}% of values match</span> : null}
        </div>
        <div className="review-card__claim">
          <span className="review-card__label">What {card.claim.by === 'ai' ? 'the AI' : card.claim.by === 'metadata' ? 'your metadata' : 'Strata'} said</span>
          <span><strong>{card.claim.label}</strong>{card.claim.role ? <span className="onto-pill">{card.claim.role}</span> : null}</span>
          {card.claim.meaning ? <span>{card.claim.meaning}</span> : null}
          {card.claim.links_to ? <span>Points at {card.claim.links_to}</span> : null}
        </div>
      </div>
      <footer className="review-card__actions">
        <Button size="sm" variant="primary" icon={<Check size={14} />} disabled={busy}
          onClick={() => onDecide(card, 'approved')}>Approve</Button>
        <Button size="sm" variant="ghost" icon={<X size={14} />} disabled={busy}
          onClick={() => onDecide(card, 'rejected')}>Reject</Button>
      </footer>
    </article>
  )
}
