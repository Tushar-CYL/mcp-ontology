import { CheckCircle2, CircleSlash, HelpCircle } from 'lucide-react'
import type { Answerable, Receipt } from '../api/types'
import { verdictTone } from '../utils/governance'
import { cx } from '../utils/cx'
import { Badge } from './Badge'

const VERDICT_TEXT = {
  yes: 'Answerable',
  partial: 'Partly answerable',
  no: 'Not answerable',
} as const

const LAYER_TITLE = {
  ontology: '1 Ontology',
  graph: '2 Graph',
  semantic: '3 Semantic',
  context: '4 Context',
} as const

/**
 * The two things that make an answer trustworthy to a non-expert: is there
 * enough evidence (yes / partial / no, with the reason), and which of the
 * four layers did it come from.
 */
export function VerdictReceipt({
  answerable,
  receipt,
}: {
  answerable?: Answerable
  receipt?: Receipt
}) {
  if (!answerable && !receipt) return null
  const Icon = answerable?.verdict === 'yes' ? CheckCircle2
    : answerable?.verdict === 'no' ? CircleSlash : HelpCircle
  return (
    <div className="verdict-receipt">
      {answerable ? (
        <div className={cx('verdict', `verdict--${answerable.verdict}`)}>
          <Badge tone={verdictTone(answerable.verdict)} icon={<Icon size={13} aria-hidden="true" />}>
            {VERDICT_TEXT[answerable.verdict]}
          </Badge>
          <span className="verdict__reason">{answerable.reason}</span>
          {answerable.nearest_metric ? (
            <span className="verdict__near">Try: <code>{answerable.nearest_metric}</code></span>
          ) : null}
        </div>
      ) : null}
      {receipt ? (
        <div className="receipt" aria-label="Layers used">
          {receipt.layers.map((item) => (
            <span
              key={item.layer}
              className={cx('receipt__layer', item.used ? 'receipt__layer--used' : 'receipt__layer--idle')}
              title={item.summary}
            >
              <strong>{LAYER_TITLE[item.layer]}</strong>
              <span>{item.summary}</span>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
