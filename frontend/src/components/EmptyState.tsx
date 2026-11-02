import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cx } from '../utils/cx'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: ReactNode
  action?: ReactNode
  compact?: boolean
  className?: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  compact = false,
  className,
}: EmptyStateProps) {
  return (
    <div className={cx('empty-state', compact && 'empty-state--compact', className)}>
      {Icon ? (
        <span className="empty-state__icon" aria-hidden="true">
          <Icon size={22} />
        </span>
      ) : null}
      <h3 className="empty-state__title">{title}</h3>
      {description ? <div className="empty-state__description">{description}</div> : null}
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  )
}
