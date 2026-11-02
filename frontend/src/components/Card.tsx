import type { ReactNode } from 'react'
import { cx } from '../utils/cx'

interface CardProps {
  title?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  /** `none` lets a table or chart run to the card edge. */
  bodyPadding?: 'default' | 'none' | 'compact'
  id?: string
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyPadding = 'default',
  id,
}: CardProps) {
  const hasHeader = Boolean(title || subtitle || actions)
  return (
    <section
      id={id}
      className={cx('card', `card--pad-${bodyPadding}`, className)}
      aria-label={typeof title === 'string' ? title : undefined}
    >
      {hasHeader ? (
        <header className="card__header">
          <div className="card__heading">
            {title ? <h2 className="card__title">{title}</h2> : null}
            {subtitle ? <p className="card__subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="card__actions">{actions}</div> : null}
        </header>
      ) : null}
      <div className={cx('card__body', `card__body--${bodyPadding}`)}>{children}</div>
    </section>
  )
}
