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

const PLAIN: Record<string, { title: string; help: string }> = {
  ontology: { title: 'Links', help: 'Other things joined to this one.' },
  graph: { title: 'Records', help: 'Real rows in the data that use this join.' },
  semantic: { title: 'Numbers', help: 'Figures calculated from this. Proposed means a person has not approved it yet.' },
  rules: { title: 'Rules', help: 'Business rules that mention this.' },
  context: { title: 'Answers', help: 'Questions and reports that used this.' },
  agents: { title: 'Agents', help: 'Agents that are allowed to read this.' },
}

function plainText(text: string): string {
  return text.replace(/[“”"]/g, '').replace(/^(Metric|Agent|Link|Rule|Note|Verified question|Report check)\s+/i, '')
}

function usefulDetail(detail: string): string {
  const text = detail.trim()
  if (!text || /^reads\b/i.test(text)) return ''
  return text.replace(/[“”"]/g, '')
}

function ImpactBody({ oid, kind, target }: { oid: string; kind: ImpactKind; target: string }) {
  const r = useAsync<ImpactResult>((signal) => api.impact(oid, kind, target, signal), [oid, kind, target])
  if (r.error) return <p className="impact__muted">{describeError(r.error).message}</p>
  if (!r.data) return <p className="impact__muted">Checking what uses this…</p>
  const d = r.data
  const name = d.target.title
  return (
    <div className="impact__body">
      <p className={cx('impact__summary', d.total ? 'is-some' : 'is-none')}>
        {d.total
          ? `If ${name} changes, ${d.total} thing${d.total === 1 ? '' : 's'} that use it change with it.`
          : `Nothing else uses ${name}. It is safe to change.`}
      </p>
      {d.tell.length ? (
        <p className="impact__tell"><Megaphone size={14} aria-hidden="true" /> Tell {d.tell.join(', ')} before you change it.</p>
      ) : null}
      {d.groups.map((g) => {
        const plain = PLAIN[g.layer] ?? { title: g.title, help: '' }
        return (
          <section key={g.layer} className="impact__group">
            <p className="impact__layer">{plain.title} <span>{g.items.length}</span></p>
            {plain.help ? <p className="impact__help">{plain.help}</p> : null}
            <ul>
              {g.items.map((item) => {
                const detail = usefulDetail(item.detail)
                return (
                  <li key={`${item.ref}|${item.text}`}>
                    <span>{plainText(item.text)}</span>
                    {detail ? <small>{detail}</small> : null}
                  </li>
                )
              })}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
