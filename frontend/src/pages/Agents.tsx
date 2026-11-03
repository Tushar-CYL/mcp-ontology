import { useEffect, useMemo, useState } from 'react'
import {
  Bot,
  Check,
  Copy,
  FlaskConical,
  KeyRound,
  Plug,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import { api, describeError } from '../api/client'
import type { Agent, AgentPreset, FeedbackKind, IssuedKey, PreviewResponse } from '../api/types'
import { AnswerView } from '../components/AnswerView'
import { VerdictReceipt } from '../components/VerdictReceipt'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Callout } from '../components/Callout'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { EvidencePanel } from '../components/EvidencePanel'
import { JsonView } from '../components/JsonView'
import { ReviewQueue } from '../components/ReviewQueue'
import { Select, TextArea, TextInput } from '../components/Field'
import { LoadingState } from '../components/LoadingState'
import { NoSourceState } from '../components/NoSourceState'
import { PageHeader } from '../components/PageHeader'
import { Table } from '../components/Table'
import { useSource } from '../context/SourceContext'
import { useToast } from '../context/ToastContext'
import { useAsync } from '../hooks/useAsync'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { agentSource, fillKey, formatLatency, keyStatus, toolLabel } from '../utils/connections'
import { cx } from '../utils/cx'

const SAMPLE_QUESTION = 'Why did West revenue fall in October 2026, and can I trust it?'

type SnippetTab = 'claude_code' | 'claude_desktop' | 'cursor' | 'powershell' | 'curl'
const SNIPPET_TABS: Array<{ id: SnippetTab; label: string }> = [
  { id: 'claude_code', label: 'Claude Code (command)' },
  { id: 'claude_desktop', label: 'Claude Desktop (config file)' },
  { id: 'cursor', label: 'Cursor / VS Code (config file)' },
  { id: 'powershell', label: 'Windows PowerShell' },
  { id: 'curl', label: 'curl (macOS / Linux / Git Bash)' },
]

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

export function Agents() {
  useDocumentTitle('Agents')
  const { selectedSource } = useSource()
  const toast = useToast()
  const source = selectedSource?.id ?? ''

  const agents = useAsync((signal) => api.agents(signal), [])
  const metrics = useAsync(
    (signal) => api.metrics(source, signal),
    [source],
    { enabled: Boolean(source) },
  )
  const approved = useMemo(
    () => (metrics.data?.metrics ?? []).filter((m) => m.status === 'approved'),
    [metrics.data],
  )

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const agentList = useMemo(() => agents.data?.agents ?? [], [agents.data])
  const selected: Agent | undefined =
    agentList.find((agent) => agent.id === selectedId) ?? agentList[0]

  // ------------------------------------------------------ register form
  const [name, setName] = useState('')
  const [purpose, setPurpose] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [preset, setPreset] = useState('insight')
  const presets = useAsync((signal) => api.agentPresets(signal), [])
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<unknown>(null)

  useEffect(() => {
    if (picked.length === 0 && approved.length > 0) {
      const revenue = approved.find((m) => m.name === 'revenue')
      setPicked([(revenue ?? approved[0]).name])
    }
  }, [approved, picked.length])

  const togglePicked = (metric: string) =>
    setPicked((current) =>
      current.includes(metric) ? current.filter((m) => m !== metric) : [...current, metric],
    )

  const register = async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const created = await api.createAgent({
        name: name.trim(),
        purpose: purpose.trim(),
        problem_statement: '',
        instructions: purpose.trim() || 'Answer with Strata context and cite every number.',
        sources: [source],
        metrics: picked,
        guardrails: [],
        skills: [],
        preset,
      })
      toast.push({ tone: 'success', title: 'Agent registered', message: created.name })
      setName('')
      setPurpose('')
      setSelectedId(created.id)
      agents.reload()
    } catch (cause) {
      setCreateError(cause)
    } finally {
      setCreating(false)
    }
  }

  if (!source) {
    return (
      <div className="page">
        <PageHeader eyebrow="Use the four layers" title="Agent connections" />
        <NoSourceState description="Connect a source first. An agent's scope is a source plus the approved metrics it may read." />
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Use the four layers"
        title="Agents"
        description="Six agent types, each built on the layers it needs. Try one here, or connect an agent you built elsewhere (Claude, Cursor, Copilot) over MCP. Every answer says which layers it used, and says plainly when the evidence is not enough."
      />

      <section className="preset-grid" aria-label="Agent types">
        {(presets.data?.presets ?? []).map((p) => (
          <button
            key={p.id}
            type="button"
            className={cx('preset-card', preset === p.id && 'preset-card--active')}
            onClick={() => setPreset(p.id)}
            aria-pressed={preset === p.id}
          >
            <span className="preset-card__title">{p.title}</span>
            <span className="preset-card__job">{p.job}</span>
            <span className="preset-card__layers">
              {p.layers.map((layer) => <span key={layer} className={`layer-chip layer-chip--${layer}`}>{LAYER_LABEL[layer]}</span>)}
            </span>
            <span className="preset-card__example">e.g. &ldquo;{p.examples[0]}&rdquo;</span>
            <span className="preset-card__meta">{p.tools.length} tools · {p.guardrails[0]}</span>
          </button>
        ))}
      </section>

      <div className="connections-layout">
        <div className="stack">
          <Card
            title="Connected agents"
            subtitle="Each agent has its own scope, keys and usage log."
            bodyPadding="compact"
            actions={
              <Button
                variant="ghost"
                size="sm"
                icon={<RefreshCw size={14} aria-hidden="true" />}
                onClick={agents.reload}
                loading={agents.loading}
              >
                Refresh
              </Button>
            }
          >
            {agents.error ? <ErrorState error={agents.error} compact /> : null}
            {agentList.length === 0 && !agents.loading ? (
              <EmptyState
                icon={Bot}
                compact
                title="No agents yet"
                description="Register the first agent below."
              />
            ) : (
              <div className="agent-list" role="list">
                {agentList.map((agent) => (
                  <button
                    key={agent.id}
                    type="button"
                    role="listitem"
                    className={cx('agent-row', selected?.id === agent.id && 'agent-row--active')}
                    onClick={() => setSelectedId(agent.id)}
                    aria-pressed={selected?.id === agent.id}
                  >
                    <Bot size={16} aria-hidden="true" />
                    <span className="agent-row__text">
                      <strong>{agent.name}</strong>
                      <span>
                        {presetTitle(presets.data?.presets, agent.preset)} · {agentSource(agent) || 'no source'} · {(agent.metrics ?? []).length} metric(s)
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </Card>

          <Card title="Register an agent" subtitle={`Scoped to source "${source}".`}>
            <p className="field__label">Agent type</p>
            <p className="preset-picked">
              <strong>{presets.data?.presets.find((p) => p.id === preset)?.title ?? preset}</strong>
              <span className="muted"> · choose another card above to change it</span>
            </p>
            <TextInput
              label="Agent name"
              required
              value={name}
              placeholder="e.g. Finance copilot"
              onChange={(event) => setName(event.target.value)}
            />
            <TextArea
              label="What it is for"
              rows={2}
              value={purpose}
              placeholder="Explains revenue movements for the finance team."
              onChange={(event) => setPurpose(event.target.value)}
            />
            <p className="field__label">Metrics it may read</p>
            {approved.length === 0 ? (
              <Callout tone="warning" title="No approved metrics">
                Approve a metric in Semantic metrics before connecting an agent.
              </Callout>
            ) : (
              <div className="metric-picker">
                {approved.map((metric) => {
                  const active = picked.includes(metric.name)
                  return (
                    <button
                      key={metric.name}
                      type="button"
                      className={active ? 'metric-pick metric-pick--active' : 'metric-pick'}
                      onClick={() => togglePicked(metric.name)}
                      aria-pressed={active}
                    >
                      <span>
                        <strong>{metric.title || metric.name}</strong>
                        <span>{metric.description}</span>
                      </span>
                      {active ? <Check size={15} aria-hidden="true" /> : null}
                    </button>
                  )
                })}
              </div>
            )}
            {createError ? <ErrorState error={createError} compact /> : null}
            <div className="form-actions">
              <Button
                variant="primary"
                icon={<Plus size={15} aria-hidden="true" />}
                loading={creating}
                disabled={!name.trim() || picked.length === 0}
                onClick={() => void register()}
              >
                Register agent
              </Button>
            </div>
          </Card>
        </div>

        <div className="stack">
          {selected ? (
            <AgentDetail
              key={selected.id}
              agent={selected}
              preset={presets.data?.presets.find((p) => p.id === (selected.preset ?? 'insight'))}
              onDeleted={() => {
                setSelectedId(null)
                agents.reload()
              }}
            />
          ) : (
            <EmptyState
              icon={Plug}
              title="Register an agent to connect it"
              description="You will get a key, copy-paste configuration for Claude Desktop, Cursor or REST, a test console and a log of every call the agent makes."
            />
          )}
          <ReviewQueue source={source} />
        </div>
      </div>
    </div>
  )
}

const LAYER_LABEL: Record<string, string> = {
  ontology: '1 Ontology', graph: '2 Graph', semantic: '3 Semantic', context: '4 Context',
}

function presetTitle(presets: AgentPreset[] | undefined, id: string | undefined): string {
  return presets?.find((p) => p.id === (id ?? 'insight'))?.title ?? 'Insight Analyst'
}

function AgentDetail({
  agent,
  preset,
  onDeleted,
}: {
  agent: Agent
  preset: AgentPreset | undefined
  onDeleted: () => void
}) {
  const toast = useToast()
  const keys = useAsync((signal) => api.agentKeys(agent.id, signal), [agent.id])
  const usage = useAsync((signal) => api.agentUsage(agent.id, signal), [agent.id])
  const connection = useAsync((signal) => api.agentConnection(agent.id, signal), [agent.id])

  const [label, setLabel] = useState('')
  const [issued, setIssued] = useState<IssuedKey | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [tab, setTab] = useState<SnippetTab>('claude_code')

  const [question, setQuestion] = useState(preset?.examples[0] ?? SAMPLE_QUESTION)
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [previewError, setPreviewError] = useState<unknown>(null)

  const issue = async () => {
    setBusy('issue')
    try {
      const created = await api.issueAgentKey(agent.id, label.trim())
      setIssued(created)
      setLabel('')
      keys.reload()
    } catch (cause) {
      toast.push({ tone: 'error', title: 'Could not issue a key', message: describeError(cause).message })
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
      toast.push({ tone: 'success', title: 'Key revoked', message: 'It stops working immediately.' })
    } catch (cause) {
      toast.push({ tone: 'error', title: 'Could not revoke', message: describeError(cause).message })
    } finally {
      setBusy(null)
    }
  }

  const copy = async (text: string, what: string) => {
    const ok = await copyText(text)
    toast.push(ok
      ? { tone: 'success', title: `${what} copied` }
      : { tone: 'error', title: 'Copy failed', message: 'Select the text and copy it manually.' })
  }

  // Two clicks, no browser dialog: the first arms the button, the second deletes.
  const [confirmDelete, setConfirmDelete] = useState(false)
  const remove = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    setBusy('delete')
    try {
      await api.deleteAgent(agent.id)
      toast.push({ tone: 'success', title: 'Agent removed', message: `${agent.name}: its keys stop working now.` })
      onDeleted()
    } catch (cause) {
      toast.push({ tone: 'error', title: 'Could not remove the agent', message: describeError(cause).message })
      setBusy(null)
    }
  }

  const runTest = async () => {
    setBusy('test')
    setPreviewError(null)
    try {
      setPreview(await api.previewAgent(agent.id, question))
    } catch (cause) {
      setPreviewError(cause)
    } finally {
      setBusy(null)
    }
  }

  const snippet = connection.data ? fillKey(connection.data.snippets[tab], issued?.key) : ''

  return (
    <>
      <Card
        title={agent.name}
        subtitle={`${preset?.title ?? 'Insight Analyst'}: ${preset?.job ?? agent.purpose ?? ''}`}
        actions={
          <div className="page-header__actions">
            <Badge tone="teal" dot>Read-only access</Badge>
            <Button
              size="sm"
              variant={confirmDelete ? 'danger' : 'ghost'}
              icon={<Trash2 size={14} aria-hidden="true" />}
              loading={busy === 'delete'}
              onClick={() => void remove()}
              onBlur={() => setConfirmDelete(false)}
            >
              {confirmDelete ? 'Click again to remove' : 'Remove'}
            </Button>
          </div>
        }
      >
        <div className="scope-grid">
          <div>
            <p className="scope-grid__label">Source</p>
            <Badge tone="indigo">{agentSource(agent) || '—'}</Badge>
          </div>
          <div>
            <p className="scope-grid__label">Metrics in scope</p>
            <div className="chip-row">
              {(agent.metrics ?? []).map((metric) => (
                <Badge key={metric} tone="neutral">{metric}</Badge>
              ))}
            </div>
          </div>
          <div>
            <p className="scope-grid__label">MCP tools</p>
            <span className="muted">{connection.data?.tools.length ?? '…'} read-only tools</span>
          </div>
        </div>
        <Callout tone="info" icon={ShieldCheck} title="Scope is enforced on every call">
          A call for another source or a metric outside this list is refused and logged.
        </Callout>
      </Card>

      <Card
        title="Keys"
        subtitle="A key is shown once. Strata stores only its hash."
        actions={<KeyRound size={16} aria-hidden="true" />}
      >
        <div className="key-issue">
          <TextInput
            label="Label"
            value={label}
            placeholder="e.g. Claude Desktop on my laptop"
            onChange={(event) => setLabel(event.target.value)}
          />
          <Button
            variant="primary"
            icon={<KeyRound size={15} aria-hidden="true" />}
            loading={busy === 'issue'}
            onClick={() => void issue()}
          >
            Issue key
          </Button>
        </div>
        {issued ? (
          <Callout tone="success" title="Copy this key now — it will not be shown again">
            <div className="secret-row">
              <code className="secret">{issued.key}</code>
              <Button
                size="sm"
                variant="secondary"
                icon={<Copy size={14} aria-hidden="true" />}
                onClick={() => void copy(issued.key, 'Key')}
              >
                Copy
              </Button>
            </div>
          </Callout>
        ) : null}
        <Table
          dense
          rows={keys.data?.keys ?? []}
          rowKey={(row) => row.id}
          empty="No keys yet. Issue one to connect this agent."
          columns={[
            { key: 'prefix', header: 'Key', render: (row) => <code>{row.prefix}…</code> },
            { key: 'label', header: 'Label', render: (row) => row.label || <span className="muted">—</span> },
            {
              key: 'status',
              header: 'Status',
              render: (row) => {
                const status = keyStatus(row)
                return <Badge tone={status.tone} dot>{status.label}</Badge>
              },
            },
            {
              key: 'used',
              header: 'Last used',
              render: (row) => <span className="muted">{row.last_used_at?.slice(0, 19).replace('T', ' ') ?? '—'}</span>,
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (row) =>
                row.revoked ? null : (
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<Trash2 size={14} aria-hidden="true" />}
                    loading={busy === row.id}
                    onClick={() => void revoke(row.id)}
                  >
                    Revoke
                  </Button>
                ),
            },
          ]}
        />
      </Card>

      <Card
        title="Connect"
        subtitle={connection.data ? <>MCP endpoint <code>{connection.data.mcp_url}</code></> : 'Loading…'}
        actions={
          snippet ? (
            <Button
              size="sm"
              variant="secondary"
              icon={<Copy size={14} aria-hidden="true" />}
              onClick={() => void copy(snippet, 'Configuration')}
            >
              Copy
            </Button>
          ) : null
        }
      >
        <div className="snippet-tabs" role="tablist" aria-label="Agent host">
          {SNIPPET_TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={cx('snippet-tab', tab === item.id && 'snippet-tab--active')}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {connection.error ? <ErrorState error={connection.error} compact /> : null}
        <pre className="code-block snippet">{snippet}</pre>
        <p className="muted">
          {tab === 'claude_desktop' || tab === 'cursor'
            ? 'This is configuration, not a command: paste it into the MCP settings file of that app. '
            : 'Run this in a terminal. '}
          {issued
            ? 'Your new key is filled in above.'
            : 'Replace <YOUR_KEY> with a key from the Keys card.'}{' '}
          Tools: {connection.data?.tools.map(toolLabel).join(', ')}.
        </p>
      </Card>

      <Card
        title="Test as this agent"
        subtitle="One question through the same governed context the agent receives. Nothing is saved."
      >
        <TextArea
          label="Question"
          rows={2}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        {preset ? (
          <div className="example-row" aria-label="Example questions">
            {preset.examples.map((example) => (
              <button key={example} type="button" className="example-chip" onClick={() => setQuestion(example)}>
                {example}
              </button>
            ))}
          </div>
        ) : null}
        {previewError ? <ErrorState error={previewError} compact /> : null}
        <div className="form-actions">
          <Button
            variant="primary"
            icon={<FlaskConical size={15} aria-hidden="true" />}
            loading={busy === 'test'}
            disabled={!question.trim()}
            onClick={() => void runTest()}
          >
            Run test
          </Button>
        </div>
        {busy === 'test' ? (
          <LoadingState label="Running" description="Collecting governed evidence before answering." compact />
        ) : null}
        {preview ? (
          <div className="stack">
            <VerdictReceipt answerable={preview.answerable} receipt={preview.receipt} />
            <AnswerView answer={preview.answer} />
            {(preview.preset ?? 'insight') === 'insight' ? (
            <EvidencePanel
              evidence={preview.evidence}
              latencyMs={preview.latency_ms}
              question={question}
              answer={preview.answer}
              agentId={agent.id}
              agentName={agent.name}
            />
            ) : (
              <details className="evidence-details">
                <summary>What the agent looked at</summary>
                <JsonView value={preview.evidence} />
              </details>
            )}
            <FeedbackForm agent={agent} question={question} answer={preview.answer} />
          </div>
        ) : null}
      </Card>

      <Card
        title="Usage"
        subtitle="Every MCP tool call made with this agent's keys."
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={14} aria-hidden="true" />}
            onClick={usage.reload}
            loading={usage.loading}
          >
            Refresh
          </Button>
        }
      >
        <Table
          dense
          rows={usage.data?.calls ?? []}
          rowKey={(row) => row.id}
          empty="No calls yet. Connect the agent and ask it a question."
          maxHeight={320}
          columns={[
            {
              key: 'when',
              header: 'When',
              render: (row) => <span className="muted">{row.created_at.slice(0, 19).replace('T', ' ')}</span>,
            },
            { key: 'tool', header: 'Tool', render: (row) => <code>{row.tool}</code> },
            { key: 'summary', header: 'Asked for', render: (row) => row.summary || <span className="muted">—</span> },
            {
              key: 'ok',
              header: 'Result',
              render: (row) =>
                row.ok ? (
                  <Badge tone="teal" dot>OK</Badge>
                ) : (
                  <Badge tone="rose" dot title={row.error ?? undefined}>
                    {row.error?.toLowerCase().startsWith('forbidden') ? 'Refused' : 'Error'}
                  </Badge>
                ),
            },
            {
              key: 'latency',
              header: 'Time',
              align: 'right',
              render: (row) => formatLatency(row.latency_ms),
            },
          ]}
        />
      </Card>
    </>
  )
}

const FEEDBACK_KINDS: Array<{ value: FeedbackKind; label: string }> = [
  { value: 'wrong_number', label: 'A number is wrong' },
  { value: 'wrong_definition', label: 'The metric definition is wrong' },
  { value: 'missing_context', label: 'Important context is missing' },
  { value: 'other', label: 'Something else' },
]

/** Phase 6: a correction goes to the steward review queue, never straight
 * into the definitions. */
function FeedbackForm({ agent, question, answer }: { agent: Agent; question: string; answer: unknown }) {
  const toast = useToast()
  const [kind, setKind] = useState<FeedbackKind>('wrong_number')
  const [correction, setCorrection] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      await api.submitFeedback({
        source: agentSource(agent),
        question,
        correction,
        kind,
        answer: typeof answer === 'string' ? answer : JSON.stringify(answer ?? ''),
        metric: agent.metrics?.[0] ?? null,
        agent_id: agent.id,
      })
      setSent(true)
      setCorrection('')
      toast.push({ tone: 'success', title: 'Sent for review', message: 'A steward decides in Context Factory → Corrections.' })
    } catch (cause) {
      toast.push({ tone: 'error', title: 'Could not send', message: describeError(cause).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="feedback-form">
      <p className="field__label">Was this answer wrong?</p>
      {sent ? (
        <Callout tone="success" title="Thanks — it is in the review queue">
          Nothing changes until a steward approves it.
        </Callout>
      ) : null}
      <Select
        label="What was wrong"
        value={kind}
        options={FEEDBACK_KINDS}
        onValueChange={(value) => setKind(value as FeedbackKind)}
      />
      <TextArea
        label="Correction"
        rows={2}
        value={correction}
        placeholder="e.g. October excludes a late batch of West orders."
        onChange={(event) => setCorrection(event.target.value)}
      />
      <div className="form-actions">
        <Button variant="secondary" loading={busy} disabled={!correction.trim()} onClick={() => void submit()}>
          Send correction for review
        </Button>
      </div>
    </div>
  )
}
