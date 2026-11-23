import { useState, type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { cx } from '../utils/cx'

/**
 * A quiet, collapsible section. Keeps secondary detail (report checks, gaps,
 * raw tables) one click away so a page leads with its real content — the
 * pattern the market uses for evidence and governance panels.
 */
export function Disclose({
  summary,
  children,
  defaultOpen = false,
  icon,
  note,
}: {
  summary: string
  children: ReactNode
  defaultOpen?: boolean
  icon?: ReactNode
  /** A short muted hint shown on the right of the summary line. */
  note?: string
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <details className="disclose" open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>
        <ChevronRight size={15} aria-hidden="true" className={cx('disclose__chev', open && 'is-open')} />
        {icon}
        <span className="disclose__label">{summary}</span>
        {note ? <span className="disclose__note">{note}</span> : null}
      </summary>
      <div className="disclose__body">{children}</div>
    </details>
  )
}
