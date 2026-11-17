import { Copy } from 'lucide-react'
import { useToast } from '../context/ToastContext'

/** A label, a value in code type and a copy button. */
export function CopyLine({ label, value }: { label: string; value: string }) {
  const toast = useToast()
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      toast.push({ title: 'Copied', message: label, tone: 'success' })
    } catch {
      toast.push({ title: 'Copy it by hand', message: value, tone: 'info' })
    }
  }
  return (
    <div className="onto-copy">
      <span className="onto-copy__label">{label}</span>
      <code className="onto-copy__value" title={value}>{value}</code>
      <button type="button" className="onto-copy__btn" onClick={copy} aria-label={`Copy ${label}`}><Copy size={14} /></button>
    </div>
  )
}
