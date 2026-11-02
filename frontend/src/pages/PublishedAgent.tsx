import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Bot, CircleHelp, MessageSquare, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import type { Agent, AskResponse } from '../api/types'
import { AnswerView } from '../components/AnswerView'
import { Badge } from '../components/Badge'
import { BeforeAfterCard } from '../components/BeforeAfterCard'
import { Button } from '../components/Button'
import { Callout } from '../components/Callout'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { EvidencePanel } from '../components/EvidencePanel'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Select, TextArea } from '../components/Field'
import { useSource } from '../context/SourceContext'
import { useAsync } from '../hooks/useAsync'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { normalizeFacts, normalizeTrace } from '../utils/evidence'

const DEFAULT_QUESTION =
  'Why did West-region revenue fall this month, which segments drove it, and can I trust the number?'

export function PublishedAgent() {
  useDocumentTitle('Published Agent')
  const { selectedSource } = useSource()
  const agentsQuery = useAsync((signal) => api.agents(signal), [])
  const agents = useMemo(
    () => (agentsQuery.data?.agents ?? []).filter((agent) => agent.status === 'published' || !agent.status),
    [agentsQuery.data],
  )

  const [agentId, setAgentId] = useState<string>('')
  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    if (agentId || agents.length === 0) return
    const preferred = agents.find((agent) => agent.status === 'published') ?? agents[0]
    setAgentId(preferred.id)
  }, [agents, agentId])

  const agent: Agent | undefined = agents.find((item) => item.id === agentId)

  const ask = async () => {
    if (!agent || !question.trim()) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.askAgent(agent.id, question.trim())
      setAnswer(result)
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  const facts = useMemo(() => normalizeFacts(answer?.evidence?.facts), [answer])
  const trace = useMemo(() => normalizeTrace(answer?.evidence?.trace), [answer])
  const firstMeasured = facts.find((fact) => fact.provenance === 'measured') ?? facts[0]

  if (agentsQuery.initialLoading) return <LoadingState label="Loading agents" />
  if (agentsQuery.error) return <ErrorState error={agentsQuery.error} onRetry={agentsQuery.reload} />

  if (agents.length === 0) {
    return (
      <div className="page">
        <PageHeader
          eyebrow="Consumption surface"
          title="Published Agent"
          description="Ask a business question and inspect the evidence behind the answer."
        />
        <EmptyState
          icon={Bot}
          title="No published agent yet"
          description="Build an agent in Agent Studio, preview it against one question, then publish. This screen will then answer with cited facts and a full trace."
          action={
            <Link to="/studio" className="btn btn--primary btn--md">
              Open Agent Studio
              <ArrowUpRight size={15} aria-hidden="true" />
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Consumption surface"
        title="Published Agent"
        description="A business question in, a cited answer out. The evidence panel shows the measured facts, the metric SQL, the relationships and every tool call."
        meta={
          <div className="page-header__chips">
            {agent ? <Badge tone="indigo" dot>{agent.name}</Badge> : null}
            {selectedSource ? <Badge tone="slate">{selectedSource.name}</Badge> : null}
            <span className="page-header__meta-text">
              {answer ? `${facts.length} facts · ${trace.length} steps` : 'Ready for a question'}
            </span>
          </div>
        }
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw size={14} aria-hidden="true" />}
            onClick={agentsQuery.reload}
          >
            Refresh agents
          </Button>
        }
      />

      <div className="grid-2 grid-2--wide-left">
        <div className="panel-stack">
          <Card
            title="Ask the agent"
            subtitle="The answer is generated from approved metrics and graph evidence. If evidence is missing, the agent must say so instead of inventing a number."
            actions={
              <Select
                label="Agent"
                value={agentId}
                options={agents.map((item) => ({ value: item.id, label: item.name }))}
                onValueChange={(value) => {
                  setAgentId(value)
                  setAnswer(null)
                }}
                className="topbar__select"
              />
            }
          >
            <TextArea
              label="Question"
              value={question}
              rows={3}
              onChange={(event) => setQuestion(event.target.value)}
              hint="Ask about a metric, a region, a period, or whether the number can be trusted."
            />
            {error ? <ErrorState error={error} compact /> : null}
            <div className="form-actions">
              <Button
                variant="primary"
                icon={<MessageSquare size={15} aria-hidden="true" />}
                loading={busy}
                onClick={() => void ask()}
              >
                Ask
              </Button>
              <Button variant="secondary" onClick={() => setQuestion(DEFAULT_QUESTION)}>
                Use a sample question
              </Button>
            </div>
            {busy ? <LoadingState label="Answering" description="Running approved skills and collecting evidence." compact /> : null}
          </Card>

          {answer ? (
            <>
              <Card title="Answer" subtitle={`Run ${answer.run_id} · ${answer.latency_ms ? Math.round(answer.latency_ms) : '—'} ms`}>
                <AnswerView answer={answer.answer} />
                <div className="provenance-split">
                  <div className="provenance-split__row">
                    <span className="provenance-split__label">Measured</span>
                    <div className="provenance-split__bar">
                      <span
                        className="provenance-split__fill provenance-split__fill--measured"
                        style={{
                          width: `${facts.length ? (facts.filter((fact) => fact.provenance === 'measured').length / facts.length) * 100 : 0}%`,
                        }}
                      />
                    </div>
                    <span className="provenance-split__value">
                      {facts.filter((fact) => fact.provenance === 'measured').length}/{facts.length}
                    </span>
                  </div>
                  <div className="provenance-split__row">
                    <span className="provenance-split__label">Derived</span>
                    <div className="provenance-split__bar">
                      <span
                        className="provenance-split__fill provenance-split__fill--derived"
                        style={{
                          width: `${facts.length ? (facts.filter((fact) => fact.provenance === 'derived').length / facts.length) * 100 : 0}%`,
                        }}
                      />
                    </div>
                    <span className="provenance-split__value">
                      {facts.filter((fact) => fact.provenance === 'derived').length}/{facts.length}
                    </span>
                  </div>
                </div>
              </Card>

              <BeforeAfterCard
                fact={firstMeasured}
                citationCount={facts.filter((fact) => fact.citation).length}
                traceCount={trace.length}
                sourceCount={answer.sources?.length ?? answer.evidence?.sources?.length ?? 0}
                confidence={answer.evidence?.confidence}
              />
            </>
          ) : (
            <EmptyState
              icon={CircleHelp}
              title="Ask one question"
              description="The published agent will return the cause, the impact and the next step, with evidence a reader can check."
            />
          )}
        </div>

        <div className="panel-stack">
          {answer ? (
            <EvidencePanel
              evidence={answer.evidence}
              sources={answer.sources}
              latencyMs={answer.latency_ms}
              runId={answer.run_id}
              question={question}
              answer={answer.answer}
              agentId={agentId}
              agentName={agent?.name ?? 'Published agent'}
            />
          ) : (
            <Card title="What the evidence panel will show" subtitle="Every claim is traceable to a tool call and a source row.">
              <ul className="detail-list">
                <li><strong>Measured facts</strong> with a citation per fact.</li>
                <li><strong>Metric definition and SQL</strong> used to compute the number.</li>
                <li><strong>Relationships and source records</strong> behind the answer.</li>
                <li><strong>Tool trace</strong>: what was looked up, compared and analysed.</li>
                <li><strong>Confidence and caveats</strong>, including missing evidence.</li>
                <li><strong>Download</strong> of the complete evidence record as JSON.</li>
              </ul>
              <Callout tone="info" title="No invented numbers">
                Even the narrative is checked: numeric claims must exist in tool evidence. If the model
                cannot cite it, the runtime falls back to a deterministic answer rather than guessing.
              </Callout>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
