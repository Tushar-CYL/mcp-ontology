import { useEffect } from 'react'
import { X, Layers } from 'lucide-react'
import { ProofMark, type Proof } from './ProofMark'

export interface Evidence {
  /** What the drawer is about, e.g. "Order 1984611 · net value". */
  title: string
  /** The honest mark for this fact. */
  proof: Proof
  /** The plain statement, e.g. "Net value is 4,210 EUR". */
  statement?: string
  /** Labelled rows: where it came from, the check, the count, who, when. */
  rows?: Array<{ k: string; v: string }>
  /** How many independent sources agree (data + rule + report + person). */
  agreedBy?: number
}

/**
 * The evidence behind one fact (plan step 1.4). Opens from any proof mark on
 * any layer and answers "why should I believe this line?": the source, the
 * check and its count, who approved it and when, and how many sources agree.
 */
export function EvidenceDrawer({ evidence, onClose }: { evidence: Evidence | null; onClose: () => void }) {
  useEffect(() => {
    if (!evidence) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [evidence, onClose])

  if (!evidence) return null
  return (
    <div className="evidence-backdrop" onClick={onClose} role="presentation">
      <aside className="evidence" aria-label="Evidence" onClick={(e) => e.stopPropagation()}>
        <div className="evidence__head">
          <span className="evidence__title">{evidence.title}</span>
          <button type="button" aria-label="Close" onClick={onClose}><X size={18} /></button>
        </div>

        <div>
          <ProofMark kind={evidence.proof} />
          {evidence.statement ? <p style={{ marginTop: 10 }}>{evidence.statement}</p> : null}
        </div>

        {typeof evidence.agreedBy === 'number' && evidence.agreedBy > 1 ? (
          <span className="evidence__agree"><Layers size={15} aria-hidden="true" /> Agreed by {evidence.agreedBy} sources</span>
        ) : null}

        <div>
          {(evidence.rows ?? []).map((r, i) => (
            <div key={`${r.k}-${i}`} className="evidence__row">
              <span className="k">{r.k}</span>
              <span>{r.v}</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  )
}
