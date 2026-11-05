import { CheckCircle2, XCircle } from 'lucide-react'
import type { EoMaturity } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Card } from '../../components/Card'

/**
 * The five levels of ontology maturity (Modern Data 101), each with the
 * checks computed from this ontology. A level counts only when it and every
 * level below it pass.
 */
export function Maturity({ card }: { card: EoMaturity }) {
  return (
    <div className="panel-stack">
      <Card title={`Level ${card.level}: ${card.level_name}`}
        subtitle="Computed from the registry, never asserted. Most ontologies stall at levels 1 and 2.">
        {card.next_steps.length ? (
          <div className="stack">
            <p className="field__label">To reach level {card.level + 1}</p>
            <ul className="eo-list">{card.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
          </div>
        ) : <p>Every level passes.</p>}
      </Card>
      <div className="eo-levels">
        {card.levels.map((level) => {
          const reached = level.level <= card.level
          return (
            <article key={level.level} className={`eo-level${reached ? ' is-reached' : ''}`}>
              <header className="eo-level__head">
                <span className="eo-level__num">{level.level}</span>
                <h3>{level.name}</h3>
                <Badge tone={reached ? 'teal' : level.passed ? 'indigo' : 'slate'}>
                  {reached ? 'Reached' : level.passed ? 'Passes, blocked below' : 'Not yet'}
                </Badge>
              </header>
              <ul className="eo-checks">
                {level.checks.map((c) => (
                  <li key={c.name} className={c.passed ? 'is-pass' : 'is-fail'}>
                    {c.passed ? <CheckCircle2 size={15} aria-label="passes" /> : <XCircle size={15} aria-label="fails" />}
                    <span><strong>{c.name}</strong> <span className="muted">{c.detail}</span></span>
                  </li>
                ))}
              </ul>
            </article>
          )
        })}
      </div>
    </div>
  )
}
