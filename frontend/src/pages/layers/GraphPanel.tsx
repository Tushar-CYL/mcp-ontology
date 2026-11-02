import { useCallback, useMemo, useState } from 'react'
import { Network, RefreshCw } from 'lucide-react'
import { api } from '../../api/client'
import type { GraphNode, SourceSummary } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Select, Toggle } from '../../components/Field'
import { KnowledgeGraph, type GraphLayout } from '../../components/KnowledgeGraph'
import { LoadingState } from '../../components/LoadingState'
import { NoSourceState } from '../../components/NoSourceState'
import { ProvenanceBadge } from '../../components/ProvenanceBadge'
import { Spinner } from '../../components/Spinner'
import { Stat } from '../../components/Stat'
import { useSource } from '../../context/SourceContext'
import { useAsync } from '../../hooks/useAsync'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { formatNumber, humanize } from '../../utils/format'

export function GraphPanel() {
  useDocumentTitle('Knowledge graph')
  const { selectedSource, loading } = useSource()

  if (loading && !selectedSource) return <LoadingState label="Loading sources" />
  if (!selectedSource) return <NoSourceState />
  return <GraphView key={selectedSource.id} source={selectedSource} />
}

function GraphView({ source }: { source: SourceSummary }) {
  const [relation, setRelation] = useState('all')
  const [budget, setBudget] = useState(160)
  const [layout, setLayout] = useState<GraphLayout>('cluster')
  const [showLabels, setShowLabels] = useState(true)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  const debouncedBudget = useDebouncedValue(budget, 350)

  const ontology = useAsync((signal) => api.ontology(source.id, signal), [source.id])
  const graph = useAsync(
    (signal) =>
      relation === 'all'
        ? api.graph(source.id, debouncedBudget, signal)
        : api.subgraph(source.id, debouncedBudget, relation, signal),
    [source.id, relation, debouncedBudget],
  )

  const nodes = graph.data?.nodes ?? []
  const edges = graph.data?.edges ?? []

  const relationNames = useMemo(() => {
    const names = new Set<string>()
    for (const item of ontology.data?.relations ?? []) names.add(item.name)
    for (const edge of edges) names.add(edge.relation)
    return [...names].sort((a, b) => a.localeCompare(b))
  }, [ontology.data, edges])

  const relationOptions = useMemo(
    () => [
      { value: 'all', label: 'All relationships' },
      ...relationNames.map((name) => ({ value: name, label: name })),
    ],
    [relationNames],
  )

  const classOrder = useMemo(() => {
    const names = new Set<string>()
    for (const cls of ontology.data?.classes ?? []) names.add(cls.name)
    for (const node of nodes) names.add(node.class)
    const countOf = (name: string) =>
      ontology.data?.classes.find((cls) => cls.name === name)?.count ?? 0
    return [...names].sort((a, b) => countOf(b) - countOf(a) || a.localeCompare(b))
  }, [ontology.data, nodes])

  const handleSelect = useCallback((node: GraphNode) => {
    setSelectedNode(node)
  }, [])

  const connections = useMemo(() => {
    if (!selectedNode) return []
    const labels = new Map(nodes.map((node) => [node.id, node.label || node.key || node.id]))
    return edges
      .filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
      .slice(0, 14)
      .map((edge) => {
        const outgoing = edge.source === selectedNode.id
        const otherId = outgoing ? edge.target : edge.source
        return {
          relation: edge.relation,
          direction: outgoing ? ('outgoing' as const) : ('incoming' as const),
          other: labels.get(otherId) ?? otherId,
          provenance: edge.provenance,
        }
      })
  }, [edges, nodes, selectedNode])

  if (graph.initialLoading) {
    return (
      <LoadingState
        label="Drawing the graph"
        description={`Fetching up to ${formatNumber(debouncedBudget)} links from the source.`}
      />
    )
  }

  if (graph.error) {
    return (
      <ErrorState
        error={graph.error}
        title="The graph could not be read"
        onRetry={graph.reload}
        extra={<p className="muted">The graph endpoint did not return a readable slice.</p>}
      />
    )
  }

  const hasEdges = edges.length > 0 && nodes.length > 0

  return (
    <div className="panel-stack">
      <Card
        title="Map controls"
        subtitle="Choose what to draw. Filters only change the rendered slice; the graph and its provenance are untouched."
        bodyPadding="compact"
      >
        <div className="graph-controls">
          <Select
            label="Relationship"
            value={relation}
            options={relationOptions}
            onValueChange={setRelation}
            hint="Filter by link type"
          />

          <div className="field graph-budget">
            <div className="field__head">
              <label className="field__label" htmlFor="edge-budget">
                Entity budget
              </label>
              <span className="field__hint">{formatNumber(budget)} links</span>
            </div>
            <input
              id="edge-budget"
              className="range"
              type="range"
              min={50}
              max={1200}
              step={50}
              value={budget}
              onChange={(event) => setBudget(Number(event.target.value))}
              aria-describedby="edge-budget-hint"
            />
            <span className="field__hint" id="edge-budget-hint">
              Larger slices show more shape; smaller slices stay readable.
            </span>
          </div>

          <Select
            label="Layout"
            value={layout}
            options={[
              { value: 'force', label: 'Relationship force' },
              { value: 'cluster', label: 'Class clusters' },
            ]}
            onValueChange={(value) => setLayout(value === 'cluster' ? 'cluster' : 'force')}
          />

          <Toggle
            label="Labels"
            description="Reader-friendly names where the data has them."
            checked={showLabels}
            onChange={setShowLabels}
          />

          <div className="graph-controls__actions">
            <Button
              variant="ghost"
              size="sm"
              icon={<RefreshCw size={14} aria-hidden="true" />}
              onClick={() => graph.reload()}
              loading={graph.loading}
            >
              Refresh
            </Button>
            {graph.loading ? <Spinner size={14} label="Updating the graph" /> : null}
          </div>
        </div>
      </Card>

      {!hasEdges ? (
        <Card title="Relationship map" bodyPadding="compact">
          <EmptyState
            icon={Network}
            title="No relationships to draw"
            description="This source has no declared foreign keys or inferable links. Its entities are still available in the Ontology layer."
          />
        </Card>
      ) : (
        <>
          <Card
            title="Relationship map"
            subtitle={`${formatNumber(nodes.length)} entities and ${formatNumber(
              edges.length,
            )} relationships in this view. Solid lines are declared; dashed lines are inferred.`}
            bodyPadding="compact"
            actions={
              <div className="chip-row">
                <Badge tone="teal" dot>
                  Declared
                </Badge>
                <Badge tone="amber" dot>
                  Inferred
                </Badge>
              </div>
            }
          >
            <KnowledgeGraph
              nodes={nodes}
              edges={edges}
              classOrder={classOrder}
              layout={layout}
              showLabels={showLabels}
              onSelect={handleSelect}
              height={560}
            />
            <p className="chart-caption">
              Scroll to zoom, drag to pan. Click an entity to inspect its key, class and
              relationships. Hover to isolate its neighbours.
            </p>
          </Card>

          <div className="stat-grid stat-grid--3">
            <Stat label="Entities in view" value={formatNumber(nodes.length)} icon={Network} tone="indigo" />
            <Stat label="Relationships in view" value={formatNumber(edges.length)} />
            <Stat
              label="Graph size"
              value={formatNumber(source.nodes)}
              hint={`${formatNumber(source.edges)} relationships in the source`}
            />
          </div>

          {selectedNode ? (
            <Card
              title={selectedNode.label || selectedNode.key || selectedNode.id}
              subtitle="Entity detail and the relationships visible in this view."
              actions={
                <Button variant="ghost" size="sm" onClick={() => setSelectedNode(null)}>
                  Clear selection
                </Button>
              }
            >
              <div className="detail-grid">
                <dl className="detail-list">
                  <div>
                    <dt>Class</dt>
                    <dd>{selectedNode.class}</dd>
                  </div>
                  <div>
                    <dt>Key</dt>
                    <dd>
                      <code className="code">{selectedNode.key ?? selectedNode.id}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>Connections</dt>
                    <dd>{formatNumber(selectedNode.degree)}</dd>
                  </div>
                  {selectedNode.source ? (
                    <div>
                      <dt>Source</dt>
                      <dd>{selectedNode.source}</dd>
                    </div>
                  ) : null}
                </dl>
                <div>
                  <p className="detail-subtitle">Visible relationships</p>
                  {connections.length === 0 ? (
                    <p className="muted">No visible relationship touches this entity.</p>
                  ) : (
                    <ul className="connection-list">
                      {connections.map((connection, index) => (
                        <li key={`${connection.relation}-${index}`} className="connection">
                          <Badge tone="slate">
                            {connection.direction === 'outgoing' ? '→' : '←'}{' '}
                            {humanize(connection.relation)}
                          </Badge>
                          <span className="connection__other">{connection.other}</span>
                          <ProvenanceBadge provenance={connection.provenance} />
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </Card>
          ) : null}
        </>
      )}
    </div>
  )
}
