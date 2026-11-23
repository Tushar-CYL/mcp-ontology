import type { ReactNode } from 'react'
import { cx } from '../utils/cx'
import { PROOF, PROOF_ORDER, type Proof } from './proof'

export type { Proof } from './proof'

/**
 * One honest mark (proved / guess / rule / disagrees / person / company),
 * the same shape and colour on every layer. Word + icon, never colour alone.
 */
export function ProofMark({
  kind,
  label,
  detail,
  size = 'md',
  className,
}: {
  kind: Proof
  /** Override the default word, e.g. "Approved by Asha · 12 Nov". */
  label?: ReactNode
  /** Extra hover text after the standard help line. */
  detail?: string
  size?: 'sm' | 'md'
  className?: string
}) {
  const d = PROOF[kind]
  const Icon = d.icon
  const title = detail ? `${d.help} — ${detail}` : d.help
  return (
    <span className={cx('proof', `proof--${kind}`, `proof--${size}`, className)} title={title}>
      <Icon size={size === 'sm' ? 13 : 15} aria-hidden="true" />
      <span className="proof__word">{label ?? d.word}</span>
    </span>
  )
}

/** The shared legend. Same component on all four pages. */
export function Legend({ only, compact }: { only?: Proof[]; compact?: boolean }) {
  const kinds = only ?? PROOF_ORDER
  return (
    <div className={cx('legend', compact && 'legend--compact')} aria-label="What the marks mean">
      {kinds.map((k) => (
        <span key={k} className="legend__item">
          <ProofMark kind={k} size="sm" />
          {!compact ? <span className="legend__help">{PROOF[k].help}</span> : null}
        </span>
      ))}
    </div>
  )
}
