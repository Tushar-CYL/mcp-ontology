import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  CheckCircle2, ChevronDown, Copy, Download, MessageSquare, MessageSquarePlus, Plus, SearchX, Send,
  ShieldCheck, Trash2, TriangleAlert, Waypoints,
} from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { OntoAsk } from '../../api/types'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { PageHeader } from '../../components/PageHeader'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { readSession } from '../../session'
import { cx } from '../../utils/cx'
import { formatCount } from '../../utils/onto'

type Cell = string | number | boolean | null
type AskRecord = { set: string; key: string; thing: string; label: string }
type AskFact = { text: string; source: string; citation: string }
type AskMetric = { name: string; title: string; owner?: string | null }
type Msg = {
  id: string
  role: 'user' | 'assistant'
  content: string
  detail?: string
  confidence?: 'high' | 'medium' | 'low'
  source?: string
  sql?: string
  columns?: string[]
  rows?: Cell[][]
  truncated?: boolean
  stamp: number
  kind?: 'answer' | 'results' | 'cards' | 'error'
  records?: AskRecord[]
  metric?: AskMetric | null
  facts?: AskFact[]
  layers?: Array<{ layer: string; what: string }>
  checks?: Array<{ name: string; passed: boolean; detail: string; severity: string }>
}
type Conv = { id: string; title: string; createdAt: number; updatedAt: number; messages: Msg[] }
type Store = { activeId: string | null; conversations: Conv[] }

function fmtCell(v: Cell): string {
  if (v === null) return ''
  if (typeof v === 'number') {
    return Number.isInteger(v) ? formatCount(v) : v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  return String(v)
}

function clock(ms: number) {
  return new Date(ms).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })
}

function userKey() {
  return (readSession()?.email || 'anonymous').trim().toLowerCase()
}

function storeKey(oid: string) {
  return `global-chat-store:${userKey()}:${oid}`
}

function loadStore(oid: string): Store {
  try {
    const raw = localStorage.getItem(storeKey(oid))
    if (raw) {
      const parsed = JSON.parse(raw) as Store
      if (parsed && Array.isArray(parsed.conversations)) {
        return {
          activeId: parsed.activeId ?? parsed.conversations[0]?.id ?? null,
          conversations: parsed.conversations.slice(0, 40),
        }
      }
    }
  } catch { /* ignore */ }
  return { activeId: null, conversations: [] }
}

function saveStore(oid: string, store: Store) {
  try {
    localStorage.setItem(storeKey(oid), JSON.stringify({
      activeId: store.activeId,
      conversations: store.conversations.slice(0, 40).map((c) => ({
        ...c, messages: c.messages.slice(-200),
      })),
    }))
  } catch { /* quota */ }
}

function titleFrom(msgs: Msg[]) {
  const q = msgs.find((m) => m.role === 'user')?.content.trim() || 'New chat'
  return q.length > 42 ? `${q.slice(0, 42)}…` : q
}

function prose(r: OntoAsk): string {
  const base = (r.explanation || '').trim()
  if (base) return /[.!?]$/.test(base) || base.includes('\n') ? base : `${base}.`
  if (r.metric?.title) return `${r.metric.title} answers this from the certified semantic layer.`
  if (r.answerable && r.things.length) {
    return `This answer uses ${r.things.join(', ')}.`
  }
  return (r.note || '').trim() || 'Not enough proven facts across the layers to answer that yet.'
}

function downloadCsv(columns: string[], rows: Cell[][], name: string) {
  const esc = (v: Cell) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const body = [columns.join(','), ...rows.map((row) => row.map(esc).join(','))].join('\n')
  const blob = new Blob([body], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Global Chat — one place for ontology, knowledge graph, semantic, and context.
 * Ontology Ask stays separate and ontology-only.
 */
export function GlobalChat() {
  useDocumentTitle('Chat')
  const { oid } = useParams()
  const navigate = useNavigate()
  const list = useAsync((signal) => api.ontoList(signal), [])
  const ontologies = useMemo(() => list.data?.ontologies ?? [], [list.data])

  useEffect(() => {
    if (oid || !ontologies.length) return
    const latest = [...ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    navigate(`/chat/${encodeURIComponent(latest.id)}`, { replace: true })
  }, [oid, ontologies, navigate])

  if (list.initialLoading && !list.data) return <div className="page page--fill"><LoadingState label="Loading" /></div>
  if (list.error) return <div className="page"><ErrorState error={list.error} onRetry={list.reload} /></div>
  if (!ontologies.length) {
    return (
      <div className="page">
        <PageHeader eyebrow="Chat" title="Chat" />
        <EmptyState icon={MessageSquare} title="Connect your data first"
          description="Global Chat answers across ontology, knowledge graph, semantic, and context. Connect data on Ontology first."
          action={<Button variant="primary" icon={<Plus size={15} />}
            onClick={() => navigate('/tools/ontology/new')}>Connect data</Button>} />
      </div>
    )
  }
  if (!oid) return <div className="page page--fill"><LoadingState label="Opening" /></div>
  const current = ontologies.find((o) => o.id === oid)
  if (!current) {
    return (
      <div className="page">
        <PageHeader eyebrow="Chat" title="Chat" />
        <EmptyState icon={SearchX} title="This data is no longer here"
          description={<>There is nothing called <code>{oid}</code>.</>}
          action={<Button variant="primary" onClick={() => navigate('/chat', { replace: true })}>Open the latest</Button>} />
      </div>
    )
  }
  return (
    <ChatWorkspace key={oid} oid={oid} name={current.name}
      choices={ontologies.map((o) => ({ id: o.id, name: o.name }))}
      onSwitch={(id) => navigate(`/chat/${encodeURIComponent(id)}`)} />
  )
}

function ChatWorkspace({ oid, name, choices, onSwitch }: {
  oid: string
  name: string
  choices: Array<{ id: string; name: string }>
  onSwitch: (id: string) => void
}) {
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [store, setStore] = useState<Store>(() => loadStore(oid))
  const end = useRef<HTMLDivElement>(null)
  const skipScroll = useRef(true)
  const active = store.conversations.find((c) => c.id === store.activeId) ?? null
  const msgs = active?.messages ?? []

  useEffect(() => {
    setStore(loadStore(oid))
    skipScroll.current = true
  }, [oid])

  useEffect(() => { saveStore(oid, store) }, [oid, store])

  useEffect(() => {
    if (skipScroll.current) { skipScroll.current = false; return }
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [msgs, busy])

  const patchActive = (updater: (msgs: Msg[]) => Msg[]) => {
    setStore((prev) => {
      let conversations = [...prev.conversations]
      let activeId = prev.activeId
      if (!activeId || !conversations.some((c) => c.id === activeId)) {
        const id = `c-${Date.now()}`
        conversations = [{ id, title: 'New chat', createdAt: Date.now(), updatedAt: Date.now(), messages: [] }, ...conversations]
        activeId = id
      }
      conversations = conversations.map((c) => {
        if (c.id !== activeId) return c
        const messages = updater(c.messages)
        return { ...c, messages, title: titleFrom(messages), updatedAt: Date.now() }
      })
      return { activeId, conversations }
    })
  }

  const newChat = () => {
    const id = `c-${Date.now()}`
    setStore((prev) => ({
      activeId: id,
      conversations: [{ id, title: 'New chat', createdAt: Date.now(), updatedAt: Date.now(), messages: [] }, ...prev.conversations],
    }))
    skipScroll.current = true
  }

  const openChat = (id: string) => {
    setStore((prev) => ({ ...prev, activeId: id }))
    skipScroll.current = true
  }

  const removeChat = (id: string) => {
    setStore((prev) => {
      const conversations = prev.conversations.filter((c) => c.id !== id)
      const activeId = prev.activeId === id ? (conversations[0]?.id ?? null) : prev.activeId
      return { activeId, conversations }
    })
  }

  const send = async (raw: string) => {
    const q = raw.trim()
    if (!q || busy) return
    const now = Date.now()
    setDraft('')
    setBusy(true)
    patchActive((prev) => [...prev, { id: `u-${now}`, role: 'user', content: q, stamp: now }])
    try {
      const r = await api.globalChat(oid, q)
      const text = prose(r)
      const stamp = Date.now()
      const showTable = Boolean(r.columns?.length && r.rows?.length)
      const records = r.records ?? []
      const facts = r.facts ?? []
      const metric = r.metric ?? null
      const layers = r.layers_used ?? []
      const next: Msg[] = [{
        id: `a-${stamp}`, role: 'assistant', kind: 'answer', stamp,
        content: text,
        detail: r.detail || undefined,
        confidence: r.confidence,
        source: r.answer_source,
        sql: r.sql || undefined,
        layers,
        checks: r.checks,
        columns: showTable ? r.columns : undefined,
        rows: showTable ? r.rows : undefined,
        truncated: r.truncated,
        metric: metric || undefined,
        records: records.length ? records : undefined,
        facts: facts.length ? facts : undefined,
      }]
      patchActive((prev) => [...prev, ...next])
    } catch (e) {
      patchActive((prev) => [...prev, {
        id: `e-${Date.now()}`, role: 'assistant', kind: 'error', stamp: Date.now(),
        content: describeError(e).message,
      }])
    } finally {
      setBusy(false)
    }
  }

  const starters = [
    'How many customers are there?',
    'Tell me about Customer Order',
    'What business rules do we have?',
    'Which certified metrics can I trust?',
  ]
  const chats = [...store.conversations].sort((a, b) => b.updatedAt - a.updatedAt)
  const who = readSession()?.email || 'this browser'

  return (
    <div className="page page--fill chat-page">
      <PageHeader
        eyebrow="Chat"
        title="Ask across every layer"
        description="Ontology, knowledge graph, semantic metrics, and context — pointed answers, SQL, and tables when the data supports them."
        actions={(
          <div className="kg-header-actions">
            {choices.length > 1 ? (
              <select className="input" value={oid} aria-label="Choose data" onChange={(e) => onSwitch(e.target.value)}>
                {choices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            ) : <span className="kg-header-meta">{name}</span>}
          </div>
        )}
      />

      <div className="onto-chat onto-chat--split chat-page__shell">
        <aside className="onto-chat__side" aria-label="Chats">
          <button type="button" className="onto-chat__new" onClick={newChat}>
            <Plus size={14} aria-hidden="true" /> New chat
          </button>
          <p className="onto-chat__side-label">Saved for {who}</p>
          <ul className="onto-chat__convos">
            {chats.map((c) => (
              <li key={c.id}>
                <button type="button" className={cx('onto-chat__convo', c.id === store.activeId && 'is-on')}
                  onClick={() => openChat(c.id)} title={c.title}>
                  <span>{c.title}</span>
                  <em>{clock(c.updatedAt)}</em>
                </button>
                <button type="button" className="onto-chat__convo-del" aria-label={`Delete ${c.title}`}
                  onClick={() => removeChat(c.id)}><Trash2 size={12} /></button>
              </li>
            ))}
            {!chats.length ? <li className="onto-chat__side-empty">No chats yet</li> : null}
          </ul>
        </aside>

        <div className="onto-chat__main">
          <div className="onto-chat__thread" aria-live="polite">
            {!msgs.length && !busy ? (
              <div className="onto-chat__empty">
                <MessageSquarePlus size={28} aria-hidden="true" />
                <h3>Global chat for {name}</h3>
                <p>
                  Ask any business question. Answers pull from ontology terms and rules,
                  live knowledge-graph records, certified metrics, and context facts.
                </p>
                <div className="onto-chat__starters">
                  {starters.map((text) => (
                    <button key={text} type="button" disabled={busy} onClick={() => void send(text)}>{text}</button>
                  ))}
                </div>
              </div>
            ) : null}
            {msgs.map((m) => <Bubble key={m.id} msg={m} />)}
            {busy ? (
              <div className="onto-chat__bubble is-assistant is-thinking">
                <span className="onto-chat__dots" aria-hidden="true"><i /><i /><i /></span>
                <span>Checking ontology, graph, metrics, and context…</span>
              </div>
            ) : null}
            <div ref={end} />
          </div>
          <form className="onto-chat__composer" onSubmit={(e) => { e.preventDefault(); void send(draft) }}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask across ontology, graph, semantic, or context…"
              aria-label="Ask a question"
              disabled={busy}
            />
            <button type="submit" aria-label="Send" disabled={busy || !draft.trim()}>
              <Send size={16} aria-hidden="true" />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

function trustLabel(msg: Msg): { ok: boolean; text: string } {
  if (msg.source === 'data' || msg.confidence === 'high') {
    return { ok: true, text: 'Verified from your data' }
  }
  if (msg.source === 'ai_checked' || msg.confidence === 'medium') {
    return { ok: true, text: 'Checked against evidence' }
  }
  if (msg.source === 'catalogue') {
    return { ok: true, text: 'From the ontology catalogue' }
  }
  if (msg.source === 'semantic') {
    return { ok: true, text: 'From the semantic layer' }
  }
  return { ok: false, text: 'Limited evidence' }
}

function Bubble({ msg }: { msg: Msg }) {
  const [page, setPage] = useState(0)
  const [showSql, setShowSql] = useState(false)
  const [showTable, setShowTable] = useState(false)
  const [showMore, setShowMore] = useState(false)
  const pageSize = 8
  const isUser = msg.role === 'user'
  const rows = msg.rows ?? []
  const columns = msg.columns ?? []
  const pages = Math.max(1, Math.ceil(rows.length / pageSize))
  const slice = rows.slice(page * pageSize, page * pageSize + pageSize)
  const single = rows.length === 1 && columns.length === 1

  if (msg.kind === 'error') {
    return (
      <div className="onto-chat__bubble is-assistant is-error is-wide">
        <p className="onto-chat__prose">{msg.content}</p>
        <time>{clock(msg.stamp)}</time>
      </div>
    )
  }

  if (isUser) {
    return (
      <div className="onto-chat__bubble is-user">
        <p className="onto-chat__prose">{msg.content}</p>
        <time>{clock(msg.stamp)}</time>
      </div>
    )
  }

  const trust = trustLabel(msg)
  const hasExtra = Boolean(msg.sql || columns.length || msg.metric || msg.records?.length || msg.facts?.length)

  return (
    <div className="onto-chat__bubble is-assistant is-wide onto-chat__answer">
      <div className={cx('onto-chat__trust', trust.ok ? 'is-ok' : 'is-warn')}>
        {trust.ok
          ? <CheckCircle2 size={14} aria-hidden="true" />
          : <TriangleAlert size={14} aria-hidden="true" />}
        <span>{trust.text}</span>
      </div>

      <p className="onto-chat__headline">{msg.content}</p>
      {msg.detail ? <p className="onto-chat__detail">{msg.detail}</p> : null}

      {msg.layers?.length ? (
        <p className="onto-chat__layers">
          {msg.layers.map((l) => l.layer).filter((v, i, a) => a.indexOf(v) === i).join(' · ')}
        </p>
      ) : null}

      {hasExtra ? (
        <div className="onto-chat__tools">
          {msg.sql ? (
            <button type="button" className={cx(showSql && 'is-on')} onClick={() => setShowSql((v) => !v)}>
              Query <ChevronDown size={13} aria-hidden="true" />
            </button>
          ) : null}
          {columns.length ? (
            <button type="button" className={cx(showTable && 'is-on')} onClick={() => setShowTable((v) => !v)}>
              Results <ChevronDown size={13} aria-hidden="true" />
            </button>
          ) : null}
          {(msg.metric || msg.records?.length || msg.facts?.length) ? (
            <button type="button" className={cx(showMore && 'is-on')} onClick={() => setShowMore((v) => !v)}>
              Evidence <ChevronDown size={13} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      ) : null}

      {showSql && msg.sql ? (
        <div className="onto-chat__sql">
          <header>
            <span>SQL</span>
            <button type="button" aria-label="Copy SQL" onClick={() => void navigator.clipboard.writeText(msg.sql!)}>
              <Copy size={12} aria-hidden="true" /> Copy
            </button>
          </header>
          <pre><code>{msg.sql}</code></pre>
        </div>
      ) : null}

      {showTable && columns.length ? (
        <div className="onto-chat__results">
          <header>
            <span>Results</span>
            <button type="button" onClick={() => downloadCsv(columns, rows, `chat-${msg.stamp}.csv`)}>
              <Download size={13} aria-hidden="true" /> CSV
            </button>
          </header>
          {single ? (
            <p className="onto-chat__single"><em>{columns[0]}</em> <strong>{fmtCell(rows[0][0])}</strong></p>
          ) : (
            <>
              <div className="onto-chat__table-wrap">
                <table>
                  <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {slice.map((row, i) => (
                      <tr key={i}>{row.map((v, j) => <td key={j} className={typeof v === 'number' ? 'num' : ''}>{fmtCell(v)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {pages > 1 ? (
                <footer>
                  <button type="button" disabled={page <= 0} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">‹</button>
                  <span>{page + 1}</span>
                  <button type="button" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} aria-label="Next page">›</button>
                  <em>{rows.length} rows{msg.truncated ? '+' : ''}</em>
                </footer>
              ) : null}
            </>
          )}
        </div>
      ) : null}

      {showMore ? (
        <div className="onto-chat__cards">
          {msg.metric ? (
            <div className="onto-chat__card onto-chat__card--metric">
              <header><ShieldCheck size={14} aria-hidden="true" /> Certified metric</header>
              <strong>{msg.metric.title || msg.metric.name}</strong>
              {msg.metric.owner ? <span>Owner {msg.metric.owner}</span> : null}
            </div>
          ) : null}
          {msg.records?.length ? (
            <div className="onto-chat__card onto-chat__card--records">
              <header><Waypoints size={14} aria-hidden="true" /> Matched records</header>
              <ul>
                {msg.records.map((r) => (
                  <li key={`${r.set}|${r.key}`}>
                    <b>{r.label}</b>
                    <small>{r.thing}</small>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {msg.facts?.length ? (
            <div className="onto-chat__card onto-chat__card--facts">
              <header>Evidence</header>
              <ul>
                {msg.facts.slice(0, 5).map((f, i) => (
                  <li key={`${f.citation}-${i}`}><span>{f.text}</span></li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <time>{clock(msg.stamp)}</time>
    </div>
  )
}
