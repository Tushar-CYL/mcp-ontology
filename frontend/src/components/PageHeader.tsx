import type { ReactNode } from 'react'
import { cx } from '../utils/cx'

interface PageHeaderProps {
  title: string
  description?: ReactNode
  eyebrow?: string
  actions?: ReactNode
  meta?: ReactNode
  className?: string
}

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  meta,
  className,
}: PageHeaderProps) {
  return (
    <header className={cx('page-header', className)}>
      <div className="page-header__main">
        {eyebrow ? <p className="page-header__eyebrow">{eyebrow}</p> : null}
        <h1 className="page-header__title">{title}</h1>
        {description ? <p className="page-header__description">{description}</p> : null}
        {meta ? <div className="page-header__meta">{meta}</div> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  )
}
