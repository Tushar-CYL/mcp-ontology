import { Badge } from './Badge'
import { Card } from './Card'
import { ProvenanceBadge } from './ProvenanceBadge'
import { formatConfidence, truncate } from '../utils/format'
import type { NormalizedFact } from '../utils/evidence'
import { cx } from '../utils/cx'

interface BeforeAfterCardProps {
  fact?: NormalizedFact
  citationCount: number
  traceCount: number
  sourceCount: number
  confidence: unknown
  className?: string
}

/**
 * A deliberately small comparison: the number on its own cannot be checked,
 * the number through this platform carries its definition, citation and
 * trace. The raw side is illustrative; the governed side is this run's data.
 */
export function BeforeAfterCard({
  fact,
  citationCount,
  traceCount,
  sourceCount,
  confidence,
  className,
}: BeforeAfterCardProps) {
  const governedText = fact
    ? truncate(fact.text, 150)
    : 'Every number this agent states is fetched through the semantic layer.'

  return (
    <Card
      title="Trust, before and after"
      subtitle="The same answer, with and without a provenance layer."
      className={cx('trust-card', className)}
      bodyPadding="compact"
    >
      <div className="trust-grid">
        <div className="trust-column trust-column--raw">
          <div className="trust-column__head">
            <span className="trust-column__label">Without the middle layer</span>
            <Badge tone="rose">Unchecked</Badge>
          </div>
          <p className="trust-column__quote">“Revenue is up 12%.”</p>
          <p className="trust-column__note">
            No definition, no date, no source. Nothing here can be checked by the person
            reading it.
          </p>
          <ul className="trust-column__list">
            <li>0 citations</li>
            <li>0 trace steps</li>
            <li>No measured fact</li>
          </ul>
        </div>
        <div className="trust-column trust-column--governed">
          <div className="trust-column__head">
            <span className="trust-column__label">Through the middle layer</span>
            <ProvenanceBadge provenance={fact?.provenance ?? 'measured'} />
          </div>
          <p className="trust-column__quote">“{governedText}”</p>
          <p className="trust-column__note">
            {fact?.citation
              ? `Cited to ${fact.citation}, produced from a defined metric and a measured row.`
              : 'Produced from a defined metric whose SQL and rows are visible.'}
          </p>
          <ul className="trust-column__list">
            <li>{citationCount} cited facts</li>
            <li>{traceCount} trace steps</li>
            <li>{sourceCount} sources</li>
            <li>{formatConfidence(confidence)} confidence</li>
          </ul>
        </div>
      </div>
      <p className="trust-card__caption">
        Before: a number with nothing behind it. After: the same number, tied to a definition,
        a citation and a trace.
      </p>
    </Card>
  )
}
