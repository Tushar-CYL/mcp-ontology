import { ArrowRight, BookOpen, ExternalLink } from 'lucide-react'
import type { CertificationLayer, CertificationResponse, SourceSummary } from '../api/types'
import { type LayerId, layerResearch } from '../content/research'
import { formatNumber } from '../utils/format'
import { Badge } from './Badge'

/** The certification report names layers slightly differently. */
const CERT_NAME: Record<LayerId, string> = {
  ontology: 'Ontology',
  graph: 'Knowledge graph',
  semantic: 'Semantic layer',
  context: 'Context',
}

function steps(layer: LayerId, source: SourceSummary, metricCount: number | null): string[] {
  const metrics = metricCount === null ? 'its' : formatNumber(metricCount)
  switch (layer) {
    case 'ontology':
      return [
        `Strata read ${formatNumber(source.tables)} tables`,
        `and found ${formatNumber(source.classes)} kinds of thing and ${formatNumber(source.relations)} links between them`,
        'so an agent can ask "What is an Order, and what does it link to?"',
      ]
    case 'graph':
      return [
        `Strata took every row of those ${formatNumber(source.classes)} kinds`,
        `and built ${formatNumber(source.nodes)} records joined by ${formatNumber(source.edges)} links, each saying where it came from`,
        'so an agent can ask "Tell me about customer c1"',
      ]
    case 'semantic':
      return [
        'Strata turned business rules into definitions',
        `and keeps ${metrics} approved metrics, each compiled to one SQL calculation with an owner and caveats`,
        'so every agent gets the same number for "What was revenue last month?"',
      ]
    case 'context':
      return [
        'For each question, Strata picks the few facts that matter',
        'cites each one, keeps under a size budget and says what it dropped',
        'and gives a verdict (yes / partial / no) so an agent refuses instead of guessing',
      ]
  }
}

function tone(status: string | undefined) {
  if (status === 'pass') return 'teal' as const
  if (status === 'warn') return 'amber' as const
  if (status === 'fail') return 'rose' as const
  return 'neutral' as const
}

export function LayerExplainer({
  layer,
  source,
  metricCount,
  certification,
  certificationLoading,
}: {
  layer: LayerId
  source: SourceSummary
  metricCount: number | null
  certification: CertificationResponse | undefined
  certificationLoading: boolean
}) {
  const research = layerResearch(layer)
  const health: CertificationLayer | undefined = certification?.layers.find(
    (item) => item.layer === CERT_NAME[layer],
  )
  const failed = health?.checks.filter((check) => !check.passed) ?? []

  return (
    <section className="layer-explainer" aria-label={`What happened in the ${research.title} layer`}>
      <div className="layer-explainer__main">
        <p className="layer-explainer__analogy">
          <strong>{research.analogy}.</strong> {research.plain}
        </p>
        <ol className="layer-steps">
          {steps(layer, source, metricCount).map((text, index) => (
            <li key={text} className="layer-step">
              <span className="layer-step__n">{index + 1}</span>
              <span>{text}</span>
              {index < 2 ? <ArrowRight size={14} aria-hidden="true" className="layer-step__arrow" /> : null}
            </li>
          ))}
        </ol>
      </div>

      <div className="layer-health" aria-live="polite">
        <p className="layer-health__title">Health check</p>
        {health ? (
          <>
            <Badge tone={tone(health.status)} dot>
              {health.status} · {health.passed}/{health.total} checks
            </Badge>
            {failed.length ? (
              <ul className="layer-health__fails">
                {failed.slice(0, 3).map((check) => (
                  <li key={check.name}>{check.name}: {check.detail}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Every check passed.</p>
            )}
            {certification?.cached ? <p className="muted">Cached result.</p> : null}
          </>
        ) : (
          <p className="muted">{certificationLoading ? 'Checking… (first check on large data can take minutes)' : 'Not checked yet.'}</p>
        )}
      </div>

      <details className="layer-research">
        <summary>
          <BookOpen size={14} aria-hidden="true" /> How others do this, and how Strata compares
        </summary>
        <div className="layer-research__body">
          <p><strong>Strata:</strong> {research.strata}</p>
          <div className="layer-research__cols">
            <div>
              <p className="layer-research__h">Companies</p>
              <ul>
                {research.companies.map((c) => (
                  <li key={c.name}>
                    <a href={c.url} target="_blank" rel="noreferrer">{c.name} <ExternalLink size={11} aria-hidden="true" /></a>
                    {' '}— {c.how}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="layer-research__h">Open-source to learn from</p>
              <ul>
                {research.repos.map((r) => (
                  <li key={r.name}>
                    <a href={r.url} target="_blank" rel="noreferrer">{r.name}</a> <span className="muted">({r.licence})</span> — {r.learn}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="layer-research__h">Evidence</p>
              <ul>
                {research.evidence.map((e) => (
                  <li key={e.url}>
                    <a href={e.url} target="_blank" rel="noreferrer">{e.claim}</a>
                    {e.bias ? <span className="layer-research__bias"> Note: {e.bias}.</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <p className="muted">Full research: docs/research/2026/REPORT.md</p>
        </div>
      </details>
    </section>
  )
}
