import { Sparkles } from 'lucide-react'
import type { Suggestions } from '../hooks/useSuggestions'
import { cx } from '../utils/cx'

/**
 * Suggestions from the data, as chips. `detailed` also shows why each one was
 * suggested (the fact from the data behind it). A chip with "..." is a
 * starter for the person to finish.
 */
export function SuggestionChips({ s, onPick, detailed = false, disabled = false, label = 'Suggestions' }: {
  s: Suggestions
  onPick: (text: string) => void
  detailed?: boolean
  disabled?: boolean
  label?: string
}) {
  if (!s.items.length) {
    return s.improving ? <p className="sugg__wait">Reading your data for suggestions...</p> : null
  }
  return (
    <div className={cx('sugg', detailed && 'sugg--detailed')} aria-label={label}>
      <p className="sugg__head">
        {s.method === 'ai'
          ? <><Sparkles size={13} aria-hidden="true" /> Picked by the AI from your data</>
          : s.improving ? 'From your data · the AI is choosing the best...' : 'From your data'}
      </p>
      <div className="sugg__list">
        {s.items.map((x) => (
          <button key={x.text} type="button" disabled={disabled} title={x.why} onClick={() => onPick(x.text)}>
            <span className="sugg__text">{x.text}</span>
            {detailed ? <span className="sugg__why">{x.why}</span> : null}
          </button>
        ))}
      </div>
    </div>
  )
}
