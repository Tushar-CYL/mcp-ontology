import type { ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { ApiError, describeError, IS_DEV } from '../api/client'
import { Badge } from './Badge'
import { Button } from './Button'
import { JsonView } from './JsonView'
import { cx } from '../utils/cx'

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
  title?: string
  compact?: boolean
  extra?: ReactNode
  className?: string
}

/**
 * One rendering for every API failure: what happened, what the service said,
 * and whether it is worth retrying. No invented data behind it.
 */
export function ErrorState({
  error,
  onRetry,
  title,
  compact = false,
  extra,
  className,
}: ErrorStateProps) {
  const description = describeError(error)
  const payload = error instanceof ApiError ? error.payload : undefined

  return (
    <div
      className={cx('error-state', compact && 'error-state--compact', className)}
      role="alert"
    >
      <span className="error-state__icon" aria-hidden="true">
        <AlertTriangle size={20} />
      </span>
      <div className="error-state__body">
        <div className="error-state__heading">
          <h3 className="error-state__title">{title ?? description.title}</h3>
          {description.status > 0 ? (
            <Badge tone="rose">{`HTTP ${description.status}`}</Badge>
          ) : null}
          <Badge tone="neutral">{description.type}</Badge>
        </div>
        <p className="error-state__message">{description.message}</p>
        {description.hint ? <p className="error-state__hint">{description.hint}</p> : null}
        {extra ? <div className="error-state__extra">{extra}</div> : null}
        {IS_DEV && payload !== undefined ? (
          <JsonView value={payload} label="Server response" className="json-view--inline" />
        ) : null}
        {onRetry ? (
          <div className="error-state__actions">
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={14} aria-hidden="true" />}
              onClick={onRetry}
            >
              Try again
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
