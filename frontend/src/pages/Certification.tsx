import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Layers,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import { api } from '../api/client'
import type { CertificationCheck, CertificationLayer, SourceSummary } from '../api/types'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Callout } from '../components/Callout'
import { Card } from '../components/Card'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { NoSourceState } from '../components/NoSourceState'
import { PageHeader } from '../components/PageHeader'
import { Stat } from '../components/Stat'
import { useSource } from '../context/SourceContext'
import { useAsync } from '../hooks/useAsync'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { formatNumber } from '../utils/format'

function toneFor(status: string): 'teal' | 'amber' | 'rose' | 'neutral' {
  if (status === 'pass') return 'teal'
  if (status === 'warn') return 'amber'
  if (status === 'fail') return 'rose'
  return 'neutral'
}

function CheckRow({ check }: { check: CertificationCheck }) {
  const Icon = check.passed ? CheckCircle2 : check.severity === 'warning' ? AlertTriangle : XCircle
  return (
    <li className={check.passed ? 'cert-check cert-check--pass' : 'cert-check cert-check--fail'}>
      <Icon size={15} aria-hidden="true" />
      <div>
        <p className="cert-check__name">{check.name}</p>
        <p className="cert-check__detail">{check.detail}</p>
      </div>
    </li>
  )
}

function LayerCard({ layer }: { layer: CertificationLayer }) {
  return (
    <Card
      title={layer.layer}
      subtitle={`${layer.passed} of ${layer.total} checks pass.`}
      actions={<Badge tone={toneFor(layer.status)} dot>{layer.status}</Badge>}
    >
      <ul className="cert-checks">
        {layer.checks.map((check) => (
          <CheckRow key={check.name} check={check} />
        ))}
      </ul>
    </Card>
  )
}

export function Certification() {
  useDocumentTitle('Certification')
  const { selectedSource, loading } = useSource()

  if (loading && !selectedSource) return <LoadingState label="Loading sources" />
  if (!selectedSource) return <NoSourceState />
  return <CertificationView source={selectedSource} />
}

function CertificationView({ source }: { source: SourceSummary }) {
  const query = useAsync(
    (signal) => (source ? api.certification(source.id, signal) : Promise.resolve(undefined)),
    [source.id],
  )
  const data = query.data
  const layers = data?.layers ?? []
  const checks = useMemo(() => layers.flatMap((layer) => layer.checks), [layers])
  const passed = checks.filter((check) => check.passed).length

  return (
    <div className="page">
      <PageHeader
        eyebrow="Layer certification"
        title="Certification"
        description="Proof that the four layers work for this source before an agent is built on top. Checks are read-only and use the same runtime as the product."
        meta={
          data ? (
            <div className="page-header__chips">
              <Badge tone={toneFor(data.status)} dot>
                {data.status}
              </Badge>
              <span className="page-header__meta-text">
                {formatNumber(passed)} of {formatNumber(checks.length)} checks pass ·{' '}
                {new Date(data.generated_at).toLocaleString()}
              </span>
            </div>
          ) : null
        }
        actions={
          <div className="page-header__actions">
            <Button
              variant="secondary"
              icon={<RefreshCw size={14} aria-hidden="true" />}
              loading={query.loading}
              onClick={query.reload}
            >
              Run again
            </Button>
            <Link to="/studio" className="btn btn--primary btn--md">
              Build an agent
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        }
      />

      {query.initialLoading ? (
        <LoadingState
          label="Certifying the four layers"
          description="Checking keys, graph edges, approved metrics and a real context pack."
        />
      ) : null}
      {query.error ? <ErrorState error={query.error} onRetry={query.reload} /> : null}

      {data ? (
        <>
          <Callout
            tone={data.status === 'pass' ? 'success' : data.status === 'fail' ? 'danger' : 'warning'}
            title={
              data.status === 'pass'
                ? 'All four layers are certified'
                : data.status === 'warn'
                  ? 'Certified with warnings'
                  : 'Certification failed'
            }
          >
            {data.status === 'pass'
              ? 'The ontology, graph, semantic layer and context pack all returned usable, cited output. An agent may be published on this source.'
              : data.status === 'warn'
                ? 'The layers are usable, but warnings should be reviewed. Publishing is allowed; fix warnings for a clean certification.'
                : 'At least one layer failed a required check. Publishing is blocked until the failing check is resolved.'}
          </Callout>

          <div className="stat-grid stat-grid--3">
            <Stat
              label="Checks passed"
              value={`${formatNumber(passed)} / ${formatNumber(checks.length)}`}
              icon={ShieldCheck}
              tone="teal"
            />
            <Stat label="Layers certified" value={`${layers.filter((layer) => layer.status !== 'fail').length} / 4`} icon={Layers} tone="indigo" />
            <Stat
              label="Metric certified"
              value={data.metric_used ?? '—'}
              hint="The approved definition used to prove the semantic layer"
            />
          </div>

          <div className="grid-2">
            {layers.map((layer) => (
              <LayerCard key={layer.layer} layer={layer} />
            ))}
          </div>

          <Card
            title="How certification is used"
            subtitle="The same checks power the gate in Agent Studio."
          >
            <div className="detail-grid">
              <div>
                <p className="detail-subtitle">Before an agent is published</p>
                <p className="muted">
                  A failing certification disables publishing in Agent Studio. A warning is shown
                  but does not block, so the user can make an informed decision.
                </p>
              </div>
              <div>
                <p className="detail-subtitle">What is checked</p>
                <ul className="detail-list">
                  <li>Classes, identities and relationship provenance</li>
                  <li>Nodes, edges and dangling links</li>
                  <li>An approved metric that executes with real SQL</li>
                  <li>A context pack with citations and a respected budget</li>
                </ul>
              </div>
            </div>
            <div className="form-actions">
              <Link to="/studio" className="btn btn--primary btn--md">
                Continue to Agent Studio
              </Link>
              <Link to="/layers/ontology" className="btn btn--secondary btn--md">
                Inspect the layers
              </Link>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  )
}
