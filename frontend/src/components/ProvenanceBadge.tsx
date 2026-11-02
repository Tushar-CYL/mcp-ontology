import { Badge } from './Badge'
import { provenanceLabel, provenanceTone } from '../utils/evidence'

interface ProvenanceBadgeProps {
  provenance: unknown
  title?: string
}

/**
 * Measured vs derived, everywhere the same: teal for measured, amber for
 * worked out. This is the product's central honesty claim, so no screen
 * leaves it to colour alone - the badge always carries words too.
 */
export function ProvenanceBadge({ provenance, title }: ProvenanceBadgeProps) {
  const value = typeof provenance === 'string' && provenance.trim() ? provenance : 'unknown'
  return (
    <Badge
      tone={provenanceTone(value)}
      dot
      title={title ?? `Provenance: ${value}`}
    >
      {provenanceLabel(value)}
    </Badge>
  )
}
