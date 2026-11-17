import { useState } from 'react'
import { Check, Copy, KeyRound, Lock, MessageSquare, Pencil, Plug, RefreshCw, Send, Trash2, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { IssuedKey, OntoAgent, OntoAgentAnswer } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { copyText } from '../../utils/download'
import { KIND_ICON } from './kinds'

/**
 * One agent, opened: ask it, see the answer and what it rests on, connect it
 * to Claude / Cursor with a key, and see what it was asked. One panel, three
 * sections, no tabs.
 */
export function AgentPanel({ agent, onClose, onCopy, onEdit, onDeleted }: {
  agent: OntoAgent
  onClose: () => void
  onCopy: () => void
  onEdit: () => void
  onDeleted: () => void
}) {
  const Icon = KIND_ICON[agent.kind]
  return (
    <aside className="ag-panel" aria-label={agent.name}>
      <header className="ag-panel__head">
        <span className="ag-panel__icon"><Icon size={18} aria-hidden="true" /></span>
        <div>
          <h2>{agent.name}</h2>
          <p>{agent.job}</p>
        </div>
        <button type="button" className="ag-panel__close" aria-label="Close" onClick={onClose}><X size={16} /></button>
      </header>
      <div className="ag-panel__meta">
        {agent.builtin
          ? <Badge tone="slate"><Lock size={11} aria-hidden="true" /> Built-in, from your data</Badge>
          : <Badge tone="indigo">Yours · version {agent.version}</Badge>}
        <Badge tone="neutral">{agent.kind_title}</Badge>
        {agent.scope.things.length ? <Badge tone="neutral">Only: {agent.scope.things.join(', ')}</Badge> : null}
        {agent.scope.metrics.length ? <Badge tone="neutral">Metrics: {agent.scope.metrics.length}</Badge> : null}
      </div>
      <div className="ag-panel__actions">
        <Button size="sm" variant="secondary" icon={<Copy size={14} />} onClick={onCopy}>
          {agent.builtin ? 'Make a copy to change it' : 'Duplicate'}
        </Button>
        {!agent.builtin ? <Button size="sm" variant="ghost" icon={<Pencil size={14} />} onClick={onEdit}>Edit</Button> : null}
        {!agent.builtin ? <DeleteButton agent={agent} onDeleted={onDeleted} /> : null}
      </div>

      <Ask agent={agent} />
      <Connect agent={agent} />
      <Usage agent={agent} />
      <details className="ag-rules">
        <summary>Rules it always follows</summary>
        <ul>{agent.guardrails.map((g) => <li key={g}>{g}</li>)}</ul>
        {agent.instructions ? <p><b>Your instructions:</b> {agent.instructions}</p> : null}
      </details>
    </aside>
  )
}

function DeleteButton({ agent, onDeleted }: { agent: OntoAgent; onDeleted: () => void }) {
  const toast = useToast()
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const remove = async () => {
    if (!armed) { setArmed(true); return }
    setBusy(true)
    try {
      await api.deleteOntoAgent(agent.id)
      toast.push({ tone: 'success', title: 'Agent deleted', message: `${agent.name}: its keys stop working now.` })
      onDeleted()
    } catch (e) {
      toast.push({ tone: 'error', title: 'Could not delete', message: describeError(e).message })
      setBusy(false)
    }
  }
  return (
    <Button size="sm" variant={armed ? 'danger' : 'ghost'} icon={<Trash2 size={14} />} loading={busy}
      onClick={() => void remove()} onBlur={() => setArmed(false)}>
      {armed ? 'Click again to delete' : 'Delete'}
    </Button>
  )
}

export function AskBox({ examples, onAsk }: {
  examples: Array<{ text: string }>
  onAsk: (q: string) => Promise<OntoAgentAnswer>
}) {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [out, setOut] = useState<OntoAgentAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const ask = async (text?: string) => {
    const question = (text ?? q).trim()
    if (!question) return
    setQ(question)
    setBusy(true)
    setError(null)
    try {
      setOut(await onAsk(question))
    } catch (e) {
      setError(describeError(e).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <form className="ag-ask" onSubmit={(e) => { e.preventDefault(); void ask() }}>
        <input className="input" value={q} maxLength={1000} aria-label="Question"
          placeholder="Ask this agent a question" onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="primary" size="sm" icon={<Send size={14} />} loading={busy} disabled={!q.trim()}>Ask</Button>
      </form>
      {examples.length ? (
        <div className="ag-examples" aria-label="Example questions from your data">
          {examples.map((e) => (
            <button key={e.text} type="button" className="example-chip" disabled={busy}
              title={e.text.includes('...') ? 'Fill in the "..." and press Ask' : 'Ask this'}
              onClick={() => (e.text.includes('...') ? setQ(e.text) : void ask(e.text))}>{e.text}</button>
          ))}
        </div>
      ) : null}
      {error ? <p className="kgb__error">{error}</p> : null}
      {out ? <AnswerCard out={out} /> : null}
    </>
  )
}

function Ask({ agent }: { agent: OntoAgent }) {
  return (
    <section className="ag-sec" aria-label="Ask">
      <h3><MessageSquare size={15} aria-hidden="true" /> Ask</h3>
      <AskBox examples={agent.examples} onAsk={(q) => api.askOntoAgent(agent.id, q)} />
    </section>
  )
}

const VERDICT: Record<string, { tone: 'teal' | 'amber' | 'rose'; label: string }> = {
  yes: { tone: 'teal', label: 'Answered' },
  partial: { tone: 'amber', label: 'Partly answered' },
  no: { tone: 'rose', label: 'Cannot answer' },
}

function cell(v: string | number | null): string {
  if (v === null || v === undefined) return '–'
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return String(v)
}

export function AnswerCard({ out }: { out: OntoAgentAnswer }) {
  const toast = useToast()
  const [applied, setApplied] = useState(false)
  const v = VERDICT[out.answerable.verdict]
  const apply = async () => {
    if (!out.proposal) return
    try {
      const oid = out.proposal.apply.split('/')[3]
      await api.ontoContext(decodeURIComponent(oid), out.proposal.text)
      setApplied(true)
      toast.push({ tone: 'success', title: 'Applied', message: 'The note is on the ontology now.' })
    } catch (e) {
      toast.push({ tone: 'error', title: 'Could not apply', message: describeError(e).message })
    }
  }
  return (
    <div className={`ag-answer is-${out.answerable.verdict}`}>
      <div className="ag-answer__top">
        <Badge tone={v.tone} dot>{v.label}</Badge>
        <span className="muted">{out.latency_ms} ms</span>
      </div>
      <p className="ag-answer__text">{out.answer.text}</p>
      {out.answerable.nearest ? <p className="muted">Nearest: {out.answerable.nearest}</p> : null}
      {out.table && out.table.rows.length > 1 ? (
        <div className="ag-table">
          <table>
            <thead><tr>{out.table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{out.table.rows.slice(0, 12).map((r, i) => (
              <tr key={i}>{r.map((x, j) => <td key={j}>{cell(x)}</td>)}</tr>
            ))}</tbody>
          </table>
          {out.table.rows.length > 12 ? <p className="muted">and {out.table.rows.length - 12} more rows</p> : null}
        </div>
      ) : null}
      {out.proposal ? (
        <div className="ag-proposal">
          {out.proposal.changes.length ? (
            <ul>{out.proposal.changes.map((c) => <li key={c.what + c.change}><b>{c.what}</b>: {c.change}</li>)}</ul>
          ) : null}
          <Button size="sm" variant="primary" icon={<Check size={14} />} disabled={applied} onClick={() => void apply()}>
            {applied ? 'Applied' : 'Apply this note'}
          </Button>
        </div>
      ) : null}
      {out.used.length ? (
        <p className="ag-used">
          {out.used.map((u) => <span key={u.layer + u.what}><b>{u.layer}</b>: {u.what}</span>)}
        </p>
      ) : null}
      {out.facts.length ? (
        <details className="ag-facts">
          <summary>What this rests on ({out.facts.length})</summary>
          <ol>{out.facts.map((f, i) => <li key={i}>{f.text} <span className="muted">· {f.source}</span></li>)}</ol>
          {out.sql ? <pre className="code-block">{out.sql}</pre> : null}
        </details>
      ) : null}
    </div>
  )
}

function Connect({ agent }: { agent: OntoAgent }) {
  const toast = useToast()
  const keys = useAsync((signal) => api.agentKeys(agent.id, signal), [agent.id])
  const conn = useAsync((signal) => api.ontoAgentConnection(agent.id, signal), [agent.id])
  const [issued, setIssued] = useState<IssuedKey | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const copy = async (text: string, what: string) => {
    const ok = await copyText(text)
    toast.push(ok ? { tone: 'success', title: `${what} copied` } : { tone: 'error', title: 'Copy it by hand' })
  }
  const issue = async () => {
    setBusy('issue')
    try {
      setIssued(await api.issueAgentKey(agent.id, 'from the Agents page'))
      keys.reload()
    } catch (e) {
      toast.push({ tone: 'error', title: 'Could not create a key', message: describeError(e).message })
    } finally {
      setBusy(null)
    }
  }
  const revoke = async (keyId: string) => {
    setBusy(keyId)
    try {
      await api.revokeAgentKey(agent.id, keyId)
      if (issued?.id === keyId) setIssued(null)
      keys.reload()
    } finally {
      setBusy(null)
    }
  }
  const live = (keys.data?.keys ?? []).filter((k) => !k.revoked)
  const cmd = conn.data ? conn.data.claude_code.replace('<YOUR_KEY>', issued?.key ?? '<YOUR_KEY>') : ''
  return (
    <section className="ag-sec" aria-label="Connect">
      <h3><Plug size={15} aria-hidden="true" /> Connect to Claude, Cursor or your code</h3>
      <p className="muted">A key lets an outside AI use this agent over MCP, with exactly these rules and nothing more.</p>
      <Button size="sm" variant="secondary" icon={<KeyRound size={14} />} loading={busy === 'issue'} onClick={() => void issue()}>
        Create a key
      </Button>
      {issued ? (
        <div className="ag-secret">
          <span>Copy it now, it is shown once:</span>
          <code>{issued.key}</code>
          <button type="button" aria-label="Copy key" onClick={() => void copy(issued.key, 'Key')}><Copy size={14} /></button>
        </div>
      ) : null}
      {conn.data ? (
        <div className="ag-cmd">
          <code>{cmd}</code>
          <button type="button" aria-label="Copy command" onClick={() => void copy(cmd, 'Command')}><Copy size={14} /></button>
        </div>
      ) : null}
      {conn.data ? <p className="muted">Tools: {conn.data.tools.join(', ')}</p> : null}
      {live.length ? (
        <ul className="ag-keys">
          {live.map((k) => (
            <li key={k.id}><code>{k.prefix}…</code> <span className="muted">{k.last_used_at ? `used ${k.last_used_at.slice(0, 16).replace('T', ' ')}` : 'not used yet'}</span>
              <Button size="sm" variant="ghost" loading={busy === k.id} onClick={() => void revoke(k.id)}>Revoke</Button></li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function Usage({ agent }: { agent: OntoAgent }) {
  const usage = useAsync((signal) => api.agentUsage(agent.id, signal), [agent.id])
  const calls = usage.data?.calls ?? []
  return (
    <section className="ag-sec" aria-label="Usage">
      <h3><RefreshCw size={15} aria-hidden="true" /> What outside AIs asked it {calls.length ? `(${calls.length})` : ''}</h3>
      {calls.length ? (
        <ul className="ag-usage">
          {calls.slice(0, 8).map((c) => (
            <li key={c.id}>
              <Badge tone={c.ok ? 'teal' : 'rose'} dot>{c.ok ? 'OK' : c.error?.toLowerCase().startsWith('forbidden') ? 'Refused' : 'Error'}</Badge>
              <code>{c.tool}</code> <span className="muted">{c.summary}</span>
            </li>
          ))}
        </ul>
      ) : <p className="muted">No calls yet.</p>}
    </section>
  )
}
