import { useMemo, useState } from 'react'
import { FileText, RefreshCw, ShieldAlert } from 'lucide-react'
import { api } from '../../api/client'
import type { ContextResponse, GraphNode, SourceSummary } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { NoSourceState } from '../../components/NoSourceState'
import { ProvenanceBadge } from '../../components/ProvenanceBadge'
import { Select } from '../../components/Field'
import { Stat } from '../../components/Stat'
import { useSource } from '../../context/SourceContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { formatNumber } from '../../utils/format'

export function ContextPanel() {
  useDocumentTitle('Context')
  const { selectedSource, loading } = useSource()

  if (loading && !selectedSource) return <LoadingState label="Loading sources" />
  if (!selectedSource) return <NoSourceState />
  return <ContextView key={selectedSource.id} source={selectedSource} />
}

function ContextView({ source }: { source: SourceSummary }) {
  const ontology = useAsync((signal) => api.ontology(source.id, signal), [source.id])
  const graph = useAsync(
    (signal) => api.graph(source.id, 300, signal),
    [source.id],
    { enabled: Boolean(source) },
  )

  const classes = ontology.data?.classes ?? []
  const nodes = graph.data?.nodes ?? []

  const [selectedClass, setSelectedClass] = useState('')
  const [selectedKey, setSelectedKey] = useState('')
  const [budget, setBudget] = useState('1200')
  const [response, setResponse] = useState<ContextResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const effectiveClass = selectedClass || classes[0]?.name || ''
  const classNodes = useMemo(
    () => nodes.filter((node: GraphNode) => node.class === effectiveClass).slice(0, 80),
    [nodes, effectiveClass],
  )
  const effectiveKey = selectedKey || classNodes[0]?.id.split(':').pop() || ''

  const facts = response?.facts ?? []
  const dropped = response?.dropped ?? []

  const analyse = async () => {
    if (!effectiveClass || !effectiveKey) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.context({
        source: source.id,
        class: effectiveClass,
        key: effectiveKey,
        budget_chars: Math.max(200, Number(budget) || 1200),
      })
      setResponse(result)
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel-stack">
      <Card
        title="One packed answer"
        subtitle="Select one entity. The packer gathers its properties, links, cross-source matches and review state, then drops whole facts until the budget fits."
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={14} aria-hidden="true" />}
            loading={busy}
            onClick={() => void analyse()}
          >
            Build pack
          </Button>
        }
      >
        <div className="form-row">
          <Select
            label="Class"
            value={effectiveClass}
            options={classes.map((item) => ({ value: item.name, label: item.name }))}
            onValueChange={(value) => {
              setSelectedClass(value)
              setSelectedKey('')
            }}
            placeholder="Choose a kind of thing"
          />
          <Select
            label="Entity"
            value={effectiveKey}
            options={classNodes.map((node) => ({
              value: node.key ?? node.key ?? node.id.split(':').pop() ?? node.id,
              label: node.label || node.id,
            }))}
            onValueChange={setSelectedKey}
            placeholder={classNodes.length === 0 ? 'No drawn entities for this class' : 'Choose an entity'}
          />
          <Select
            label="Budget"
            value={budget}
            options={[
              { value: '600', label: '600 characters' },
              { value: '1200', label: '1,200 characters' },
              { value: '2400', label: '2,400 characters' },
              { value: '4800', label: '4,800 characters' },
            ]}
            onValueChange={setBudget}
          />
        </div>
        <Callout tone="info">
          The pack is deterministic. A measurement outranks an inference; a fact that does not fit
          is dropped whole, never cut in half, and the dropped list is shown.
        </Callout>
        {error ? <ErrorState error={error} compact /> : null}
      </Card>

      {busy ? <LoadingState label="Packing evidence" compact /> : null}
      {!response && !busy ? (
        <EmptyState
          icon={FileText}
          title="No context pack yet"
          description="Choose a class and an entity, then build the pack. Every line will carry a provenance label and a citation."
        />
      ) : null}

      {response ? (
        <>
          <div className="stat-grid stat-grid--3">
            <Stat label="Facts kept" value={formatNumber(facts.length)} />
            <Stat label="Dropped" value={formatNumber(dropped.length)} hint="Budget forced a choice" />
            <Stat
              label="Review pending"
              value={formatNumber(response.review_pending)}
              hint="Semantic or context decisions waiting"
            />
          </div>

          {response.focus && (
            <Card title="Focus" subtitle="What this pack is about." bodyPadding="compact">
              <div className="chip-row">
                <Badge tone="indigo">{typeof response.focus === 'string' ? response.focus : response.focus.class}</Badge>
                <Badge tone="slate">
                  {typeof response.focus === 'string' ? '' : response.focus.key}
                </Badge>
                <Badge tone="neutral">{response.chars} characters used</Badge>
              </div>
            </Card>
          )}

          <Card title="Facts kept" subtitle="Each fact is whole, labelled and cited.">
            <div className="fact-list">
              {facts.map((fact, index) => (
                <div className="fact" key={`${fact.text}-${index}`}>
                  <div className="fact__head">
                    <ProvenanceBadge provenance={fact.provenance ?? 'unknown'} />
                    {fact.citation ? <span className="fact__citation">{fact.citation}</span> : <span className="fact__no-citation">no citation</span>}
                  </div>
                  <p className="fact__text">{fact.text}</p>
                  {fact.as_of ? <p className="fact__as-of">as at {String(fact.as_of)}</p> : null}
                </div>
              ))}
            </div>
          </Card>

          {dropped.length > 0 ? (
            <Card title="Dropped from the pack" subtitle="Shown, not silently discarded.">
              <div className="fact-list">
                {dropped.map((fact, index) => (
                  <div className="fact fact--dropped" key={`${fact.text}-${index}`}>
                    <div className="fact__head">
                      <ProvenanceBadge provenance={fact.provenance ?? 'unknown'} />
                      <span className="fact__no-citation">dropped</span>
                    </div>
                    <p className="fact__text">{fact.text}</p>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}

          {response.review_pending > 0 ? (
            <Callout tone="warning" title="Review pending">
              {response.review_pending} semantic/context proposal(s) are waiting for a human decision.
              The pack says so; it does not pretend the definitions are final.
            </Callout>
          ) : null}

          <Card title="Rendered pack" subtitle="Exactly what an agent receives.">
            <pre className="code-block">{response.rendered}</pre>
          </Card>
        </>
      ) : null}

      {ontology.error ? <ErrorState error={ontology.error} compact /> : null}
      {graph.error ? (
        <Callout tone="warning" title="Graph sample unavailable">
          Entity choices are limited until the graph sample loads. <ShieldAlert size={14} aria-hidden="true" />
        </Callout>
      ) : null}
    </div>
  )
}
