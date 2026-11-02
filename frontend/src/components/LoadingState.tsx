import { Spinner } from './Spinner'
import { cx } from '../utils/cx'

interface LoadingStateProps {
  label?: string
  description?: string
  compact?: boolean
}

export function LoadingState({ label = 'Loading', description, compact = false }: LoadingStateProps) {
  return (
    <div
      className={cx('loading-state', compact && 'loading-state--compact')}
      role="status"
      aria-live="polite"
    >
      <Spinner size={compact ? 18 : 22} label={label} />
      <div className="loading-state__text">
        <p className="loading-state__label">{label}…</p>
        {description ? <p className="loading-state__description">{description}</p> : null}
      </div>
    </div>
  )
}
