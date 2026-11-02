import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { AlertTriangle, CircleAlert, CircleCheck, Info } from 'lucide-react'
import { cx } from '../utils/cx'

type CalloutTone = 'info' | 'success' | 'warning' | 'danger'

const ICONS: Record<CalloutTone, LucideIcon> = {
  info: Info,
  success: CircleCheck,
  warning: AlertTriangle,
  danger: CircleAlert,
}

interface CalloutProps {
  children: ReactNode
  tone?: CalloutTone
  title?: ReactNode
  icon?: LucideIcon
  className?: string
}

export function Callout({ children, tone = 'info', title, icon, className }: CalloutProps) {
  const Icon = icon ?? ICONS[tone]
  return (
    <div className={cx('callout', `callout--${tone}`, className)} role={tone === 'danger' ? 'alert' : 'note'}>
      <Icon className="callout__icon" size={17} aria-hidden="true" />
      <div className="callout__body">
        {title ? <p className="callout__title">{title}</p> : null}
        <div className="callout__text">{children}</div>
      </div>
    </div>
  )
}
