import { useState } from 'react'
import { Check, ClipboardCheck, X } from 'lucide-react'
import { api, describeError } from '../api/client'
import type { FeedbackItem } from '../api/types'
import { useToast } from '../context/ToastContext'
import { useAsync } from '../hooks/useAsync'
import { humanize } from '../utils/format'
import { Badge } from './Badge'
import { Button } from './Button'
import { Card } from './Card'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'

function tone(status: string) {
  if (status === 'approved') return 'teal' as const
  if (status === 'rejected') return 'rose' as const
  return 'amber' as const
}

function describe(item: FeedbackItem): string {
  const proposal = item.proposal
  if (proposal?.type === 'synonym') {
    return `Add synonym "${proposal.synonym}" to ${proposal.metric}`
  }
  return item.correction
}

/**
 * Everything waiting for a person: Steward proposals and "this answer was
 * wrong" corrections. Accepting a synonym proposal applies it; nothing else
 * changes a definition by itself, and every decision is audited.
 */
export function ReviewQueue({ source }: { source: string }) {
  const toast = useToast()
  const [pendingOnly, setPendingOnly] = useState(true)
  const items = useAsync((signal) => api.feedback(source, pendingOnly, signal), [source, pendingOnly])
  const [busy, setBusy] = useState<string | null>(null)

  const decide = async (item: FeedbackItem, decision: 'approved' | 'rejected') => {
    setBusy(item.id + decision)
    try {
      const result = await api.decideFeedback(item.id, decision)
      toast.push({
        tone: 'success',
        title: decision === 'approved' ? 'Accepted' : 'Rejected',
        message: result.applied ?? undefined,
      })
      items.reload()
    } catch (cause) {
      toast.push({ tone: 'error', title: 'Could not record the decision', message: describeError(cause).message })
    } finally {
      setBusy(null)
    }
  }

  const list = items.data?.items ?? []
  return (
    <Card
      title="Waiting for review"
      subtitle="Steward proposals and corrections. Nothing changes until a person accepts it."
      actions={
        <Button size="sm" variant="ghost" onClick={() => setPendingOnly((v) => !v)}>
          {pendingOnly ? 'Show all' : 'Pending only'}
        </Button>
      }
    >
      {items.error ? <ErrorState error={items.error} compact /> : null}
      {list.length === 0 && !items.loading ? (
        <EmptyState
          icon={ClipboardCheck}
          compact
          title={pendingOnly ? 'Nothing waiting' : 'Nothing yet'}
          description='Ask a Steward agent, e.g. "sales" means revenue, or mark an answer as wrong in the test console.'
        />
      ) : (
        <div className="correction-list">
          {list.map((item) => (
            <article className="correction" key={item.id}>
              <header className="correction__head">
                <Badge tone={tone(item.status)} dot>{item.status}</Badge>
                <Badge tone="neutral">{item.kind === 'proposal' ? 'Steward proposal' : humanize(item.kind)}</Badge>
                {item.metric ? <Badge tone="indigo">{item.metric}</Badge> : null}
                <span className="muted">{item.created_at.slice(0, 16).replace('T', ' ')}</span>
              </header>
              <p className="correction__fix">{describe(item)}</p>
              {item.kind !== 'proposal' ? (
                <p className="correction__q muted">Question: {item.question}</p>
              ) : null}
              {item.status === 'proposed' ? (
                <div className="form-actions">
                  <Button
                    size="sm"
                    variant="primary"
                    icon={<Check size={14} aria-hidden="true" />}
                    loading={busy === item.id + 'approved'}
                    onClick={() => void decide(item, 'approved')}
                  >
                    Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<X size={14} aria-hidden="true" />}
                    loading={busy === item.id + 'rejected'}
                    onClick={() => void decide(item, 'rejected')}
                  >
                    Reject
                  </Button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </Card>
  )
}
