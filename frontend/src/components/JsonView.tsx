import { useMemo, useState } from 'react'
import { Check, ChevronDown, ChevronRight, Copy } from 'lucide-react'
import { copyText } from '../utils/download'
import { cx } from '../utils/cx'

interface JsonViewProps {
  value: unknown
  label?: string
  defaultOpen?: boolean
  className?: string
  maxHeight?: number
}

function toText(value: unknown): string {
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2) ?? 'null'
  } catch {
    return String(value)
  }
}

/** Collapsible, copyable JSON payload (SQL params, trace steps, errors). */
export function JsonView({
  value,
  label = 'JSON',
  defaultOpen = false,
  className,
  maxHeight,
}: JsonViewProps) {
  const [open, setOpen] = useState(defaultOpen)
  const [copied, setCopied] = useState(false)
  const text = useMemo(() => toText(value), [value])

  const handleCopy = async () => {
    if (await copyText(text)) {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1_600)
    }
  }

  return (
    <div className={cx('json-view', className)}>
      <div className="json-view__bar">
        <button
          type="button"
          className="json-view__toggle"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
        >
          {open ? (
            <ChevronDown size={14} aria-hidden="true" />
          ) : (
            <ChevronRight size={14} aria-hidden="true" />
          )}
          <span>{label}</span>
        </button>
        <button
          type="button"
          className="json-view__copy"
          onClick={() => void handleCopy()}
          aria-label={`Copy ${label}`}
        >
          {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      {open ? (
        <pre
          className="json-view__code"
          tabIndex={0}
          style={maxHeight ? { maxHeight } : undefined}
        >
          <code>{text}</code>
        </pre>
      ) : null}
    </div>
  )
}
