import type { Proof } from '../components/proof'

/**
 * Map the many provenance words the backend uses onto the six proof marks the
 * UI shows (see components/ProofMark.tsx). One place, so every layer agrees.
 */
const PROVENANCE: Record<string, Proof> = {
  measured: 'proved',
  declared: 'proved',
  exact: 'proved',
  stated: 'proved',
  observed: 'proved',
  verified: 'proved',
  derived: 'rule',
  inferred: 'rule',
  rule: 'rule',
  guessed: 'guess',
  proposed: 'guess',
  unknown: 'guess',
  external: 'guess',
  estimated: 'guess',
  conflict: 'disagrees',
  disagrees: 'disagrees',
  approved: 'person',
  company: 'company',
}

export function proofFromProvenance(provenance?: string | null): Proof {
  return PROVENANCE[(provenance ?? 'unknown').toLowerCase()] ?? 'guess'
}
