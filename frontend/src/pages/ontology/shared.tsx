import { useEffect, useRef, useState } from 'react'
import { Check, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { EoItem, EoJob } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { useToast } from '../../context/ToastContext'

export function StatusBadge({ status }: { status: EoItem['status'] }) {
  const tone = status === 'approved' ? 'teal' : status === 'rejected' ? 'rose' : 'amber'
  const label = status === 'proposed' ? 'Proposed' : status === 'approved' ? 'Approved' : 'Rejected'
  return <Badge tone={tone} dot>{label}</Badge>
}

/** Approve / reject one proposal. Decided items show who decided. */
export function ItemActions({ oid, item, by, onDone, onEdit }: {
  oid: string
  item: EoItem
  by: string
  onDone: () => void
  onEdit?: () => void
}) {
  const toast = useToast()
  const [busy, setBusy] = useState<string | null>(null)
  const decide = async (decision: 'approved' | 'rejected') => {
    setBusy(decision)
    try {
      await api.eoDecide(oid, { kind: item.kind, key: item.key, decision, by })
      onDone()
    } catch (error) {
      toast.push({ title: 'Not saved', message: describeError(error).message, tone: 'error' })
    } finally {
      setBusy(null)
    }
  }
  if (item.status !== 'proposed') {
    return (
      <span className="eo-actions">
        <StatusBadge status={item.status} />
        {onEdit ? <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button> : null}
      </span>
    )
  }
  return (
    <span className="eo-actions">
      <Button size="sm" variant="secondary" icon={<Check size={14} />} loading={busy === 'approved'}
        onClick={() => decide('approved')} aria-label={`Approve ${item.key}`}>Approve</Button>
      <Button size="sm" variant="ghost" icon={<X size={14} />} loading={busy === 'rejected'}
        onClick={() => decide('rejected')} aria-label={`Reject ${item.key}`}>Reject</Button>
      {onEdit ? <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button> : null}
    </span>
  )
}

/** Approve every proposal of a kind, optionally only confident ones. */
export function BulkApprove({ oid, kind, by, items, minConfidence = 0, label, onDone }: {
  oid: string
  kind: string
  by: string
  items: EoItem[]
  minConfidence?: number
  label?: string
  onDone: () => void
}) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const eligible = items.filter((i) => i.status === 'proposed'
    && (i.confidence ?? 0) >= minConfidence).length
  if (!eligible) return null
  const run = async () => {
    setBusy(true)
    try {
      const out = await api.eoApproveAll(oid, kind, by, minConfidence)
      toast.push({ title: `Approved ${out.approved.length}`, tone: 'success' })
      onDone()
    } catch (error) {
      toast.push({ title: 'Not approved', message: describeError(error).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button size="sm" variant="primary" loading={busy} onClick={run}>
      {label ?? 'Approve all'} ({eligible})
    </Button>
  )
}

/** Live log of a background job, polled until it ends. */
export function JobLog({ jobId, onFinished }: { jobId: string; onFinished: (job: EoJob) => void }) {
  const [job, setJob] = useState<EoJob | null>(null)
  const done = useRef(onFinished)
  done.current = onFinished
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const tick = async () => {
      try {
        const next = await api.eoJob(jobId)
        if (!active) return
        setJob(next)
        if (next.status === 'running') timer = setTimeout(tick, 700)
        else done.current(next)
      } catch {
        if (active) timer = setTimeout(tick, 1500)
      }
    }
    void tick()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [jobId])
  return (
    <ol className="load-steps eo-job" aria-live="polite">
      {(job?.steps ?? [{ t: 0, text: 'starting' }]).map((step, i) => (
        <li key={i}><span className="muted">{step.t.toFixed(1)}s</span> {step.text}</li>
      ))}
      {job?.status === 'failed' ? <li className="eo-job__error">{job.error}</li> : null}
    </ol>
  )
}

export function Evidence({ lines, max = 2 }: { lines: string[]; max?: number }) {
  if (!lines.length) return null
  const shown = lines.slice(0, max)
  return (
    <ul className="eo-evidence">
      {shown.map((line, i) => <li key={i}>{line}</li>)}
      {lines.length > max ? <li className="muted">+{lines.length - max} more</li> : null}
    </ul>
  )
}
