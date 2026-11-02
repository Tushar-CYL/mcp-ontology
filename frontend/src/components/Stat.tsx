import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cx } from '../utils/cx'

export type StatTone = 'default' | 'indigo' | 'teal' | 'amber' | 'rose'

interface StatProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: LucideIcon
  tone?: StatTone
  className?: string
}

export function Stat({ label, value, hint, icon: Icon, tone = 'default', className }: StatProps) {
  return (
    <div className={cx('stat', `stat--${tone}`, className)}>
      <div className="stat__head">
        {Icon ? <Icon className="stat__icon" size={15} aria-hidden="true" /> : null}
        <span className="stat__label">{label}</span>
      </div>
      <div className="stat__value">{value}</div>
      {hint ? <div className="stat__hint">{hint}</div> : null}
    </div>
  )
}
