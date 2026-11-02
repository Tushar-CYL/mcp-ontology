import type { ReactNode } from 'react'
import { cx } from '../utils/cx'

export type BadgeTone = 'neutral' | 'indigo' | 'teal' | 'amber' | 'rose' | 'slate'

interface BadgeProps {
  children: ReactNode
  tone?: BadgeTone
  dot?: boolean
  icon?: ReactNode
  title?: string
  className?: string
}

export function Badge({
  children,
  tone = 'neutral',
  dot = false,
  icon,
  title,
  className,
}: BadgeProps) {
  return (
    <span className={cx('badge', `badge--${tone}`, className)} title={title}>
      {dot ? <span className="badge__dot" aria-hidden="true" /> : null}
      {icon ? (
        <span className="badge__icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children}
    </span>
  )
}
