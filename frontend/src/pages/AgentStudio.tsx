import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bot,
  Check,
  FlaskConical,
  Plus,
  Rocket,
  ShieldCheck,
  Sparkles,
  Wand2,
} from 'lucide-react'
import { api } from '../api/client'
import type {
  Agent,
  AgentDraft,
  CertificationResponse,
  PreviewResponse,
  SkillDefinition,
} from '../api/types'
import { AnswerView } from '../components/AnswerView'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Callout } from '../components/Callout'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { EvidencePanel } from '../components/EvidencePanel'
import { Select, TextArea, TextInput } from '../components/Field'
import { LoadingState } from '../components/LoadingState'
import { NoSourceState } from '../components/NoSourceState'
import { PageHeader } from '../components/PageHeader'
import { Spinner } from '../components/Spinner'
import { useSource } from '../context/SourceContext'
import { useToast } from '../context/ToastContext'
import { useAsync } from '../hooks/useAsync'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

const DEFAULT_QUESTION =
  'Why did West-region revenue fall this month, which segments drove it, and can I trust the number?'

const DEFAULT_GUARDRAILS = [
  'Use only metrics with an approved definition.',
  'Never state a number that is not in the evidence.',
  'Stay within the selected data source.',
]

function guardrailText(guardrail: unknown): string {
  if (typeof guardrail === 'string') return guardrail
  if (guardrail && typeof guardrail === 'object' && 'instruction' in guardrail) {
    return String((guardrail as { instruction?: unknown }).instruction ?? '')
  }
  return ''
}

function agentDraftFrom(agent: Agent, source: string): AgentDraft {
  const stored = agent as Agent & { source_id?: string }
  return {
    name: agent.name,
    purpose: agent.purpose ?? '',
    problem_statement: agent.problem_statement ?? '',
    instructions: agent.instructions ?? '',
    sources: agent.sources ?? [stored.source_id ?? agent.source ?? source],
    metrics: agent.metrics ?? [],
    guardrails: (agent.guardrails ?? []).map(guardrailText).filter(Boolean),
    skills: agent.skills ?? [],
  }
}

function blankDraft(source: string, metrics: string[]): AgentDraft {
  return {
    name: 'West Revenue Analyst',
    purpose: 'Explain revenue changes and show the evidence behind the number.',
    problem_statement:
      'Revenue fell in the West region. Show which segments drove the change, whether the number can be trusted, and what to inspect next.',
    instructions:
      'You are a finance analyst for the West region. Explain revenue changes using only approved metrics and cited evidence. Always say whether the number can be trusted and what to inspect next.',
    sources: [source],
    metrics: metrics.length > 0 ? [metrics[0]] : [],
    guardrails: [...DEFAULT_GUARDRAILS],
    skills: ['explain_metric', 'compare_periods', 'breakdown_by', 'graph_context', 'evidence_search'],
  }
}

function statusTone(status?: string): 'teal' | 'amber' | 'rose' | 'neutral' {
  if (status === 'pass' || status === 'published') return 'teal'
  if (status === 'warn' || status === 'draft') return 'amber'
  if (status === 'fail') return 'rose'
  return 'neutral'
}

export function AgentStudio() {
  useDocumentTitle('Agent Studio')
  const { selectedSource, loading: sourceLoading } = useSource()
  const toast = useToast()
  const agents = useAsync((signal) => api.agents(signal), [])
  const metrics = useAsync(
    (signal) =>
      selectedSource
        ? api.metrics(selectedSource.id, signal)
        : Promise.resolve({ metrics: [] }),
    [selectedSource?.id],
    { enabled: Boolean(selectedSource) },
  )
  const skills = useAsync(
    (signal) =>
      selectedSource
        ? api.skills(selectedSource.id, signal)
        : Promise.resolve({ skills: [] }),
    [selectedSource?.id],
    { enabled: Boolean(selectedSource) },
  )
  const certification = useAsync(
    (signal) =>
      selectedSource
        ? api.certification(selectedSource.id, signal)
        : Promise.resolve(null),
    [selectedSource?.id],
    { enabled: Boolean(selectedSource) },
  )
  const sourceGuardrails = useAsync(
    (signal) =>
      selectedSource
        ? api.sourceGuardrails(selectedSource.id, signal)
        : Promise.resolve({ source_id: '', rules: [] }),
    [selectedSource?.id],
    { enabled: Boolean(selectedSource) },
  )

  const [agentId, setAgentId] = useState<string | null>(null)
  const [draft, setDraft] = useState<AgentDraft>(() =>
    blankDraft(selectedSource?.id ?? '', []),
  )
  const [guardrailInput, setGuardrailInput] = useState('')
  const [sourceGuardrailInput, setSourceGuardrailInput] = useState('')
  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [busy, setBusy] = useState<
    'save' | 'preview' | 'publish' | 'suggest' | 'skill' | 'source-guardrail' | null
  >(null)
  const [error, setError] = useState<unknown>(null)
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [status, setStatus] = useState<string>('draft')
  const [customSkill, setCustomSkill] = useState<{
    name: string
    kind: 'metric_focus' | 'comparison' | 'breakdown'
    metric: string
    dimension: string
  }>({ name: '', kind: 'metric_focus', metric: '', dimension: '' })

  const metricList = metrics.data?.metrics ?? []
  const skillList = skills.data?.skills ?? []
  const certificationData: CertificationResponse | null =
    certification.data && typeof certification.data === 'object' && 'layers' in certification.data
      ? (certification.data as CertificationResponse)
      : null

  useEffect(() => {
    if (!selectedSource) return
    setDraft((current) =>
      current.sources.includes(selectedSource.id)
        ? current
        : { ...current, sources: [selectedSource.id] },
    )
  }, [selectedSource])

  useEffect(() => {
    if (metricList.length === 0) return
    setDraft((current) =>
      current.metrics.length > 0
        ? current
        : { ...current, metrics: [metricList[0].name] },
    )
    setCustomSkill((current) =>
      current.metric ? current : { ...current, metric: metricList[0].name },
    )
  }, [metricList])

  const selectedMetricDefinition = useMemo(
    () => metricList.find((metric) => metric.name === draft.metrics[0]),
    [metricList, draft.metrics],
  )

  const selectAgent = (id: string) => {
    const agent = agents.data?.agents.find((item) => item.id === id)
    if (!agent) return
    setAgentId(agent.id)
    setDraft(agentDraftFrom(agent, selectedSource?.id ?? ''))
    setStatus(agent.status ?? 'draft')
    setPreview(null)
  }

  const save = async (): Promise<Agent | null> => {
    if (!draft.name.trim()) {
      setError(new Error('Give the agent a name.'))
      return null
    }
    if (draft.metrics.length === 0) {
      setError(new Error('Attach at least one approved metric.'))
      return null
    }
    setBusy('save')
    setError(null)
    try {
      const saved = agentId
        ? await api.updateAgent(agentId, draft)
        : await api.createAgent(draft)
      setAgentId(saved.id)
      setStatus(saved.status ?? 'draft')
      agents.reload()
      toast.push({ tone: 'success', title: 'Agent saved', message: saved.name })
      return saved
    } catch (cause) {
      setError(cause)
      return null
    } finally {
      setBusy(null)
    }
  }

  const runPreview = async () => {
    if (!question.trim()) return
    setBusy('preview')
    setError(null)
    try {
      const saved = agentId ? { id: agentId } : await save()
      if (!saved) return
      setPreview(await api.previewAgent(saved.id, question.trim()))
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(null)
    }
  }

  const publish = async () => {
    if (certificationData?.status === 'fail') {
      setError(
        new Error('Layer certification failed. Resolve the failing checks before publishing.'),
      )
      return
    }
    setBusy('publish')
    setError(null)
    try {
      const saved = agentId ? { id: agentId } : await save()
      if (!saved) return
      const result = await api.publishAgent(saved.id)
      setStatus(result.status)
      agents.reload()
      toast.push({
        tone: 'success',
        title: 'Agent published',
        message: 'The published agent is ready for questions.',
      })
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(null)
    }
  }

  const suggestGuardrails = async () => {
    if (!draft.problem_statement.trim()) {
      setError(new Error('Write the problem statement first so guardrails can be suggested.'))
      return
    }
    setBusy('suggest')
    setError(null)
    try {
      const result = await api.suggestGuardrails({
        problem_statement: draft.problem_statement,
        source_id: selectedSource?.id,
        metrics: draft.metrics,
      })
      const additions = result.guardrails
        .map((item) => item.instruction)
        .filter((text) => text && !draft.guardrails.includes(text))
      setDraft((current) => ({
        ...current,
        guardrails: [...current.guardrails, ...additions].slice(0, 14),
      }))
      toast.push({
        tone: 'success',
        title: 'Guardrails suggested',
        message: result.configured
          ? 'Review and edit them before saving.'
          : 'Offline suggestions were generated. Review and edit them before saving.',
      })
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(null)
    }
  }

  const addGuardrail = () => {
    const text = guardrailInput.trim()
    if (!text) return
    setDraft((current) => ({
      ...current,
      guardrails: current.guardrails.includes(text)
        ? current.guardrails
        : [...current.guardrails, text],
    }))
    setGuardrailInput('')
  }

  const toggleSkill = (skill: string) => {
    setDraft((current) => ({
      ...current,
      skills: current.skills.includes(skill)
        ? current.skills.filter((item) => item !== skill)
        : [...current.skills, skill],
    }))
  }

  const toggleMetric = (name: string) => {
    setDraft((current) => {
      const active = current.metrics.includes(name)
      if (active && current.metrics.length === 1) return current
      return {
        ...current,
        metrics: active
          ? current.metrics.filter((item) => item !== name)
          : [...current.metrics, name].slice(0, 4),
      }
    })
  }

  const sourceRules = sourceGuardrails.data?.rules ?? []

  const addSourceGuardrail = async () => {
    const sourceId = selectedSource?.id
    const text = sourceGuardrailInput.trim()
    if (!sourceId || !text) return
    setBusy('source-guardrail')
    setError(null)
    try {
      await api.saveSourceGuardrails(sourceId, [
        ...sourceRules.map((rule) => rule.instruction),
        text,
      ])
      setSourceGuardrailInput('')
      sourceGuardrails.reload()
      toast.push({
        tone: 'success',
        title: 'Source guardrail saved',
        message: 'Every agent on this source inherits this rule.',
      })
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(null)
    }
  }

  const removeSourceGuardrail = async (instruction: string) => {
    const sourceId = selectedSource?.id
    if (!sourceId) return
    setBusy('source-guardrail')
    setError(null)
    try {
      await api.saveSourceGuardrails(
        sourceId,
        sourceRules
          .map((rule) => rule.instruction)
          .filter((text) => text !== instruction),
      )
      sourceGuardrails.reload()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(null)
    }
  }

  const createSkill = async () => {
    if (!selectedSource || !customSkill.name.trim() || !customSkill.metric) {
      setError(new Error('A custom skill needs a name, a metric and a source.'))
      return
    }
    setBusy('skill')
    setError(null)
    try {
      const created = await api.createSkill({
        name: customSkill.name.trim(),
        description: `Custom ${customSkill.kind.replace('_', ' ')} for ${customSkill.metric}.`,
        source_id: selectedSource.id,
        kind: customSkill.kind,
        metric: customSkill.metric,
        dimension: customSkill.dimension,
      })
      skills.reload()
      setDraft((current) => ({
        ...current,
        skills: current.skills.includes(created.id)
          ? current.skills
          : [...current.skills, created.id],
      }))
      setCustomSkill({
        name: '',
        kind: 'metric_focus',
        metric: customSkill.metric,
        dimension: '',
      })
      toast.push({ tone: 'success', title: 'Custom skill created', message: created.name })
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(null)
    }
  }

  const deleteSkill = async (skill: SkillDefinition) => {
    if (skill.builtin) return
    try {
      await api.deleteSkill(skill.id)
      setDraft((current) => ({
        ...current,
        skills: current.skills.filter((item) => item !== skill.id),
      }))
      skills.reload()
    } catch (cause) {
      setError(cause)
    }
  }

  if (sourceLoading && !selectedSource) return <LoadingState label="Loading sources" />
  if (!selectedSource) return <NoSourceState />

  return (
    <div className="page">
      <PageHeader
        eyebrow="Build a governed agent"
        title="Agent Studio"
        description="Define a problem, give the agent instructions, choose approved metrics and skills, set guardrails, test it, then publish. Every answer is built from the four certified layers."
        actions={
          <div className="page-header__actions">
            <Button
              variant="secondary"
              icon={<Check size={15} aria-hidden="true" />}
              loading={busy === 'save'}
              onClick={() => void save()}
            >
              Save
            </Button>
            <Button
              variant="primary"
              icon={<Rocket size={15} aria-hidden="true" />}
              loading={busy === 'publish'}
              disabled={certificationData?.status === 'fail'}
              onClick={() => void publish()}
            >
              Publish
            </Button>
          </div>
        }
      />

      <div className="grid-2 grid-2--wide-left">
        <div className="panel-stack">
          <Card
            title="Problem and instructions"
            subtitle={`Source scope: ${selectedSource.name || selectedSource.id}. The agent cannot read outside this source.`}
          >
            <div className="form-row">
              <TextInput
                label="Agent name"
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                required
              />
              <Select
                label="Edit an existing agent"
                value={agentId ?? ''}
                options={(agents.data?.agents ?? []).map((agent) => ({
                  value: agent.id,
                  label: `${agent.name} (${agent.status ?? 'draft'})`,
                }))}
                placeholder="Create a new agent"
                onValueChange={(value) => {
                  if (value) selectAgent(value)
                  else {
                    setAgentId(null)
                    setDraft(
                      blankDraft(
                        selectedSource.id,
                        metricList.map((metric) => metric.name),
                      ),
                    )
                    setStatus('draft')
                    setPreview(null)
                  }
                }}
              />
            </div>
            <TextArea
              label="Problem statement"
              value={draft.problem_statement}
              rows={3}
              onChange={(event) =>
                setDraft({ ...draft, problem_statement: event.target.value })
              }
              hint="The business question this agent exists to answer. Guardrail suggestions use it."
            />
            <TextInput
              label="Purpose"
              value={draft.purpose}
              onChange={(event) => setDraft({ ...draft, purpose: event.target.value })}
              hint="One sentence a business user would understand."
            />
            <TextArea
              label="Instructions"
              value={draft.instructions}
              rows={5}
              onChange={(event) =>
                setDraft({ ...draft, instructions: event.target.value })
              }
              hint="How the agent should reason, what it must always explain, and what it must refuse."
            />
          </Card>

          <Card
            title="Data scope and metrics"
            subtitle="Only approved definitions from this source can be used. Attach up to four."
            actions={
              <Link to="/certification" className="link-button">
                Layer certification
              </Link>
            }
          >
            <div className="scope-strip">
              <span className="scope-strip__label">Source</span>
              <Badge tone="indigo" dot>
                {selectedSource.name || selectedSource.id}
              </Badge>
              <span className="scope-strip__meta">
                {selectedSource.origin} · {selectedSource.classes} classes ·{' '}
                {selectedSource.relations} relationships
              </span>
            </div>

            <div className="source-rules">
              <div className="source-rules__head">
                <span className="detail-subtitle">Source guardrails</span>
                <Badge tone="slate">{sourceRules.length} inherited</Badge>
              </div>
              <p className="muted">
                These rules belong to the data source and apply to every agent built on it.
              </p>
              {sourceRules.length === 0 ? (
                <p className="muted">No source-specific guardrails yet.</p>
              ) : (
                <ul className="guardrail-list">
                  {sourceRules.map((rule) => (
                    <li key={rule.id} className="guardrail">
                      <ShieldCheck size={15} aria-hidden="true" />
                      <span>{rule.instruction}</span>
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => void removeSourceGuardrail(rule.instruction)}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="form-row">
                <TextInput
                  label="Add a source guardrail"
                  placeholder="Never expose customer contact details."
                  value={sourceGuardrailInput}
                  onChange={(event) => setSourceGuardrailInput(event.target.value)}
                />
                <div className="form-actions">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Plus size={14} aria-hidden="true" />}
                    loading={busy === 'source-guardrail'}
                    onClick={() => void addSourceGuardrail()}
                  >
                    Add to source
                  </Button>
                </div>
              </div>
            </div>

            {metrics.initialLoading ? <Spinner size={16} label="Loading metrics" /> : null}
            {metricList.length === 0 ? (
              <Callout tone="warning" title="No approved metrics">
                Run layer certification or create an approved semantic definition before
                building an agent.
              </Callout>
            ) : (
              <div className="metric-picker">
                {metricList.map((metric) => {
                  const active = draft.metrics.includes(metric.name)
                  return (
                    <button
                      key={metric.name}
                      type="button"
                      className={active ? 'metric-pick metric-pick--active' : 'metric-pick'}
                      onClick={() => toggleMetric(metric.name)}
                      aria-pressed={active}
                    >
                      <span>
                        <strong>{metric.title || metric.name}</strong>
                        <span>{metric.description}</span>
                      </span>
                      <Badge tone={metric.status === 'approved' ? 'teal' : 'amber'}>
                        {metric.status}
                      </Badge>
                    </button>
                  )
                })}
              </div>
            )}
          </Card>

          <Card
            title="Guardrails"
            subtitle="Enforceable rules. Defaults are always on; add domain rules in natural language."
            actions={
              <div className="chip-row">
                <Badge tone="teal" icon={<ShieldCheck size={13} aria-hidden="true" />}>
                  {draft.guardrails.length} active
                </Badge>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Wand2 size={14} aria-hidden="true" />}
                  loading={busy === 'suggest'}
                  onClick={() => void suggestGuardrails()}
                >
                  Suggest with AI
                </Button>
              </div>
            }
          >
            <ul className="guardrail-list">
              {draft.guardrails.map((guardrail) => (
                <li key={guardrail} className="guardrail">
                  <ShieldCheck size={15} aria-hidden="true" />
                  <span>{guardrail}</span>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        guardrails: draft.guardrails.filter((item) => item !== guardrail),
                      })
                    }
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <div className="form-row">
              <TextInput
                label="Add a guardrail"
                placeholder="Never compare across regions without naming both."
                value={guardrailInput}
                onChange={(event) => setGuardrailInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    addGuardrail()
                  }
                }}
              />
              <div className="form-actions">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Plus size={14} aria-hidden="true" />}
                  onClick={addGuardrail}
                >
                  Add
                </Button>
              </div>
            </div>
          </Card>

          <Card
            title="Skills"
            subtitle="Predefined analysis tools plus your own safe recipes. Each call returns cited evidence."
          >
            <div className="skill-grid">
              {skillList.map((skill) => {
                const active = draft.skills.includes(skill.id)
                return (
                  <button
                    key={skill.id}
                    type="button"
                    className={active ? 'skill skill--active' : 'skill'}
                    aria-pressed={active}
                    onClick={() => toggleSkill(skill.id)}
                  >
                    <Sparkles size={15} aria-hidden="true" />
                    <span>
                      <strong>{skill.label || skill.name || skill.id}</strong>
                      <span>{skill.description}</span>
                    </span>
                    {active ? <Check size={15} aria-hidden="true" /> : null}
                  </button>
                )
              })}
            </div>
            {skillList.some((skill) => !skill.builtin) ? (
              <div className="custom-skill-list">
                {skillList
                  .filter((skill) => !skill.builtin)
                  .map((skill) => (
                    <span key={skill.id} className="custom-skill">
                      <Badge tone="indigo">{skill.label || skill.name}</Badge>
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => void deleteSkill(skill)}
                      >
                        Delete
                      </button>
                    </span>
                  ))}
              </div>
            ) : null}

            <div className="custom-skill-builder">
              <p className="detail-subtitle">Create a custom skill</p>
              <div className="form-row">
                <TextInput
                  label="Skill name"
                  placeholder="West region focus"
                  value={customSkill.name}
                  onChange={(event) =>
                    setCustomSkill({ ...customSkill, name: event.target.value })
                  }
                />
                <Select
                  label="Analysis"
                  value={customSkill.kind}
                  options={[
                    { value: 'metric_focus', label: 'Metric focus' },
                    { value: 'comparison', label: 'Period comparison' },
                    { value: 'breakdown', label: 'Dimension breakdown' },
                  ]}
                  onValueChange={(value) =>
                    setCustomSkill({
                      ...customSkill,
                      kind: value as typeof customSkill.kind,
                    })
                  }
                />
                <Select
                  label="Metric"
                  value={customSkill.metric}
                  options={metricList.map((metric) => ({
                    value: metric.name,
                    label: metric.title || metric.name,
                  }))}
                  onValueChange={(value) =>
                    setCustomSkill({ ...customSkill, metric: value })
                  }
                />
                <Select
                  label="Dimension (optional)"
                  value={customSkill.dimension}
                  options={(selectedMetricDefinition?.dimensions ?? []).map(
                    (dimension) => ({ value: dimension, label: dimension }),
                  )}
                  placeholder="No dimension"
                  onValueChange={(value) =>
                    setCustomSkill({ ...customSkill, dimension: value })
                  }
                />
              </div>
              <div className="form-actions">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Plus size={14} aria-hidden="true" />}
                  loading={busy === 'skill'}
                  onClick={() => void createSkill()}
                >
                  Create skill
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <div className="panel-stack">
          <Card
            title="Layer certification"
            subtitle="The four layers must be usable before this agent can be published."
            actions={
              certificationData ? (
                <Badge tone={statusTone(certificationData.status)} dot>
                  {certificationData.status}
                </Badge>
              ) : null
            }
          >
            {certification.initialLoading ? (
              <Spinner size={16} label="Certifying layers" />
            ) : certificationData ? (
              <div className="cert-mini">
                {certificationData.layers.map((layer) => (
                  <div className="cert-mini__row" key={layer.layer}>
                    <span>{layer.layer}</span>
                    <span className="cert-mini__checks">
                      {layer.passed}/{layer.total} checks
                    </span>
                    <Badge tone={statusTone(layer.status)}>{layer.status}</Badge>
                  </div>
                ))}
                <Link to="/certification" className="link-button">
                  Open full certification
                </Link>
              </div>
            ) : (
              <ErrorState error={certification.error} compact />
            )}
          </Card>

          <Card
            title="Test before publishing"
            subtitle="One question, the full trace, the facts and the answer. A preview is not a published run."
            actions={
              <Badge tone={status === 'published' ? 'teal' : 'amber'}>{status}</Badge>
            }
          >
            <TextArea
              label="Question"
              value={question}
              rows={3}
              onChange={(event) => setQuestion(event.target.value)}
            />
            {error ? <ErrorState error={error} compact /> : null}
            <div className="form-actions">
              <Button
                variant="primary"
                icon={<FlaskConical size={15} aria-hidden="true" />}
                loading={busy === 'preview'}
                onClick={() => void runPreview()}
              >
                Run preview
              </Button>
              <Button variant="secondary" onClick={() => setQuestion(DEFAULT_QUESTION)}>
                Reset question
              </Button>
            </div>
            {busy === 'preview' ? (
              <LoadingState
                label="Running the agent"
                description="Tool calls are collected before the answer is written."
                compact
              />
            ) : null}
          </Card>

          {preview ? (
            <>
              <Card title="Answer" subtitle="Cause, impact and the recommended next step.">
                <AnswerView answer={preview.answer} />
                <p className="muted">
                  {preview.latency_ms ? `${Math.round(preview.latency_ms)} ms · ` : ''}
                  The narrative may be model-written; the numbers and citations are not.
                </p>
              </Card>
              <EvidencePanel
                evidence={preview.evidence}
                latencyMs={preview.latency_ms}
                question={question}
                answer={preview.answer}
                agentId={agentId ?? 'draft-agent'}
                agentName={draft.name}
              />
              {status === 'published' ? (
                <Callout tone="success" title="Published">
                  Open <Link to={`/agent/${agentId}`}>the published agent</Link> to ask a
                  question and share the evidence trace.
                </Callout>
              ) : null}
            </>
          ) : (
            <EmptyState
              icon={Bot}
              title="Preview an answer"
              description="Run one sample question. You will see the answer, the measured facts, the citations and every tool call before publishing."
            />
          )}
        </div>
      </div>
    </div>
  )
}
