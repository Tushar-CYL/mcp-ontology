import { Download } from 'lucide-react'
import { api } from '../../api/client'
import type { EoAuditEntry } from '../../api/types'
import { Button } from '../../components/Button'
import { Disclose } from '../../components/Disclose'
import { useAsync } from '../../hooks/useAsync'

const when = (at?: string) =>
  at ? new Date(at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : ''

const line = (e: EoAuditEntry) =>
  `${e.decision} ${e.kind}${e.key ? ` ${e.key}` : ''}`.trim()

/**
 * Who decided what, when and why: every approval, rule and edit in one list,
 * downloadable. It makes the people side of trust auditable without a big card.
 */
export function DecisionLog({ oid }: { oid: string }) {
  const log = useAsync<{ audit: EoAuditEntry[] }>((signal) => api.eoAudit(oid, signal), [oid])
  const rows = log.data?.audit ?? []

  const download = () => {
    const head = 'when,who,decision,note\n'
    const body = rows.map((e) =>
      [when(e.at), e.by, line(e), (e.note ?? '').replace(/"/g, '""')]
        .map((c) => `"${c}"`).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob([head + body], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `decisions-${oid}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Disclose summary="Decision log" note={rows.length ? `${rows.length} decisions` : 'Nothing decided yet'}>
      {!rows.length ? (
        <p className="muted">No decisions recorded yet. Approvals, rules and edits appear here with who and when.</p>
      ) : (
        <>
          <div className="onto-row" style={{ justifyContent: 'flex-end', marginBottom: 8 }}>
            <Button size="sm" variant="ghost" icon={<Download size={14} />} onClick={download}>Download CSV</Button>
          </div>
          <ul className="decisionlog">
            {rows.slice(0, 50).map((e, i) => (
              <li key={`${e.at}-${i}`}>
                <span className="decisionlog__what"><b>{line(e)}</b>{e.note ? ` — ${e.note}` : ''}</span>
                <span className="decisionlog__who">{[e.by, when(e.at)].filter(Boolean).join(' · ')}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Disclose>
  )
}
