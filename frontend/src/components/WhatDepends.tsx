import { useState } from 'react'
import { ChevronDown, ChevronRight, GitFork, Megaphone } from 'lucide-react'
import { api, describeError } from '../api/client'
import type { ImpactKind, ImpactResult } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { cx } from '../utils/cx'

/**
 * Impact analysis, where a change is made: everything across the layers that
 * depends on a field, metric, thing or rule, and who to tell. Read only.
 * `open` shows it straight away (used while a field is being edited).
 */
export function WhatDepends({ oid, kind, target, open: startOpen = false, compact = false }: {
  oid: string
  kind: ImpactKind
  target: string
  open?: boolean
  compact?: boolean
}) {
  const [open, setOpen] = useState(startOpen)
  return (
    <div className={cx('impact', compact && 'impact--compact')}>
      <button type="button" className="impact__toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
        <GitFork size={14} aria-hidden="true" /> What depends on this?
      </button>
      {open ? <ImpactBody oid={oid} kind={kind} target={target} /> : null}
    </div>
  )
}

function ImpactBody({ oid, kind, target }: { oid: string; kind: ImpactKind; target: string }) {
  const r = useAsync<ImpactResult>((signal) => api.impact(oid, kind, target, signal), [oid, kind, target])
  if (r.error) return <p className="impact__muted">{describeError(r.error).message}</p>
  if (!r.data) return <p className="impact__muted">Looking across every layer…</p>
  const d = r.data
  return (
    <div className="impact__body">
      <p className={cx('impact__summary', d.total ? 'is-some' : 'is-none')}>{d.summary}.</p>
      {d.tell.length ? (
        <p className="impact__tell"><Megaphone size={14} aria-hidden="true" /> Tell before you change it: <strong>{d.tell.join(', ')}</strong></p>
      ) : null}
      {d.groups.map((g) => (
        <div key={g.layer} className="impact__group">
          <p className="impact__layer">{g.title} <span>{g.items.length}</span></p>
          <ul>
            {g.items.map((i) => (
              <li key={`${i.ref}|${i.text}`}><span>{i.text}</span>{i.detail ? <small>{i.detail}</small> : null}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
