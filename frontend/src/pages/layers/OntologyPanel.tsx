import { useMemo } from 'react'
import { Boxes, GitBranch, Link2, RefreshCw, ShieldCheck } from 'lucide-react'
import { api } from '../../api/client'
import type { OntologyClass, OntologyRelation, SourceSummary } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { ConfidenceMeter } from '../../components/ConfidenceMeter'
import { OntologyDiagram } from '../../components/OntologyDiagram'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { NoSourceState } from '../../components/NoSourceState'
import { ProvenanceBadge } from '../../components/ProvenanceBadge'
import { Stat } from '../../components/Stat'
import { Table, type Column } from '../../components/Table'
import { colorFor } from '../../config/palette'
import { useSource } from '../../context/SourceContext'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { isMeasured } from '../../utils/evidence'
import { formatNumber } from '../../utils/format'

export function OntologyPanel() {
  useDocumentTitle('Ontology')
  const { selectedSource, loading } = useSource()

  if (loading && !selectedSource) return <LoadingState label="Loading sources" />
  if (!selectedSource) return <NoSourceState />
  return <OntologyView key={selectedSource.id} source={selectedSource} />
}

function MeasureChips({ measures }: { measures: string[] }) {
  if (!measures || measures.length === 0) {
    return <span className="muted">—</span>
  }
  const shown = measures.slice(0, 3)
  const rest = measures.length - shown.length
  return (
    <div className="chip-row">
      {shown.map((measure) => (
        <Badge key={measure} tone="slate">
          {measure}
        </Badge>
      ))}
      {rest > 0 ? (
        <Badge tone="neutral" title={measures.join(', ')}>
          +{rest}
        </Badge>
      ) : null}
    </div>
  )
}

function OntologyView({ source }: { source: SourceSummary }) {
  const ontology = useAsync((signal) => api.ontology(source.id, signal), [source.id])
  const data = ontology.data
  const classes = useMemo(() => data?.classes ?? [], [data])
  const relations = useMemo(() => data?.relations ?? [], [data])

  const sortedClasses = useMemo(
    () => [...classes].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
    [classes],
  )
  const sortedRelations = useMemo(
    () => [...relations].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
    [relations],
  )
  const statedCount = relations.filter((relation) => isMeasured(relation.provenance)).length
  const derivedCount = relations.length - statedCount

  const classColumns = useMemo<Array<Column<OntologyClass>>>(
    () => [
      {
        key: 'name',
        header: 'Kind of thing',
        render: (row) => (
          <span className="cell-inline">
            <span
              className="class-dot"
              style={{ background: colorFor(sortedClasses.indexOf(row)) }}
              aria-hidden="true"
            />
            <span className="cell-title">{row.name}</span>
          </span>
        ),
      },
      {
        key: 'table',
        header: 'From table',
        render: (row) => <code className="code">{row.table || '—'}</code>,
      },
      {
        key: 'key',
        header: 'Identified by',
        render: (row) => (
          <span className="cell-inline">
            <code className="code">{row.key || '—'}</code>
            {row.key_is_synthetic ? (
              <Badge tone="amber" title="No key column existed, so one was constructed">
                invented
              </Badge>
            ) : null}
          </span>
        ),
      },
      {
        key: 'time',
        header: 'Dated by',
        render: (row) =>
          row.time_column ? (
            <code className="code">{row.time_column}</code>
          ) : (
            <span className="muted">—</span>
          ),
      },
      {
        key: 'count',
        header: 'Things',
        align: 'right',
        render: (row) => <span className="num">{formatNumber(row.count)}</span>,
      },
      {
        key: 'measures',
        header: 'Measures',
        render: (row) => <MeasureChips measures={row.measures ?? []} />,
      },
    ],
    [sortedClasses],
  )

  const relationColumns = useMemo<Array<Column<OntologyRelation>>>(
    () => [
      {
        key: 'name',
        header: 'Kinds of link',
        render: (row) => <code className="code code--strong">{row.name}</code>,
      },
      {
        key: 'domain',
        header: 'From',
        render: (row) => <span className="cell-title">{row.domain}</span>,
      },
      {
        key: 'range',
        header: 'To',
        render: (row) => <span className="cell-title">{row.range}</span>,
      },
      {
        key: 'provenance',
        header: 'How we know',
        render: (row) => (
          <ProvenanceBadge
            provenance={row.provenance}
            title={
              isMeasured(row.provenance)
                ? 'The source declared this link'
                : 'Inferred from column names or structure, not declared'
            }
          />
        ),
      },
      {
        key: 'confidence',
        header: 'Confidence',
        render: (row) => <ConfidenceMeter value={row.confidence} compact />,
      },
      {
        key: 'count',
        header: 'Links',
        align: 'right',
        render: (row) => <span className="num">{formatNumber(row.count)}</span>,
      },
    ],
    [],
  )

  if (ontology.initialLoading) {
    return <LoadingState label="Reading the ontology" description="Classes, keys and links are being worked out from the source." />
  }

  if (ontology.error) {
    return (
      <ErrorState
        error={ontology.error}
        onRetry={ontology.reload}
        title="The ontology could not be read"
      />
    )
  }

  if (!data) return null

  const isEmpty = classes.length === 0 && relations.length === 0

  return (
    <div className="panel-stack">
      <div className="stat-grid">
        <Stat label="Kinds of thing" value={formatNumber(classes.length)} icon={Boxes} tone="indigo" hint="Classes discovered from tables" />
        <Stat label="Kinds of link" value={formatNumber(relations.length)} icon={Link2} hint="Relations discovered between classes" />
        <Stat label="Declared links" value={formatNumber(statedCount)} icon={ShieldCheck} tone="teal" hint="The source stated them" />
        <Stat label="Inferred links" value={formatNumber(derivedCount)} icon={GitBranch} tone="amber" hint="Worked out, with confidence" />
      </div>

      {isEmpty ? (
        <Card title="What exists here" bodyPadding="compact">
          <EmptyState
            icon={Boxes}
            title="No classes were discovered"
            description="The source connected, but nothing in it looked like a table with rows. Warnings from the source may explain why."
          />
        </Card>
      ) : (
        <>
          {derivedCount > 0 ? (
            <Callout
              tone="warning"
              title={`${derivedCount} of ${relations.length} links were inferred, not declared`}
            >
              A real database declares its keys; most CSV exports declare nothing. Inferred links
              carry their confidence and are drawn dashed in the graph. They are strong
              inferences, not facts.
            </Callout>
          ) : (
            <Callout tone="success" title="Every link was declared by the source">
              No inference was needed to connect these kinds. Each link can be traced back to a
              foreign key or an explicit reference.
            </Callout>
          )}

          <Card
            title="Schema map"
            subtitle="The classes the source exposes and the relationships between them. Hover a class to isolate its links."
            bodyPadding="compact"
          >
            <OntologyDiagram classes={sortedClasses} relations={sortedRelations} />
          </Card>

          <Card
            title="Kinds of thing"
            subtitle="Every class, the table it came from, and how one is identified."
            actions={
              <button type="button" className="link-button" onClick={() => ontology.reload()}>
                <RefreshCw size={13} aria-hidden="true" />
                Refresh
              </button>
            }
            bodyPadding="none"
          >
            <Table
              columns={classColumns}
              rows={sortedClasses}
              rowKey={(row) => row.name}
              caption="Classes discovered from the source"
              empty="No classes were discovered."
            />
          </Card>

          <Card
            title="Kinds of link"
            subtitle="Provenance and confidence on every link — this is the part most tools hide."
            bodyPadding="none"
          >
            <Table
              columns={relationColumns}
              rows={sortedRelations}
              rowKey={(row) => row.name}
              caption="Relations between classes, with how each was established"
              empty="No links were found between these kinds."
            />
          </Card>
        </>
      )}
    </div>
  )
}
