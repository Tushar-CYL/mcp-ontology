import { useMemo } from 'react'
import { Download, FileJson, GitBranch, Link2 } from 'lucide-react'
import type { Evidence } from '../api/types'
import { useToast } from '../context/ToastContext'
import { downloadJson } from '../utils/download'
import {
  buildEvidenceRecord,
  isMeasured,
  normalizeFacts,
  normalizeTrace,
} from '../utils/evidence'
import { formatAsOf, formatLatency, formatNumber, formatValue, humanize } from '../utils/format'
import { Badge } from './Badge'
import { Button } from './Button'
import { Card } from './Card'
import { ConfidenceMeter } from './ConfidenceMeter'
import { EmptyState } from './EmptyState'
import { ProvenanceBadge } from './ProvenanceBadge'
import { cx } from '../utils/cx'

export interface EvidencePanelProps {
  evidence: Evidence | undefined
  sources?: string[]
  latencyMs?: number | null
  runId?: string
  question: string
  answer: unknown
  agentId: string
  agentName: string
  className?: string
}

function safeFilename(part: string): string {
  return part.replace(/[^a-z0-9-_]+/gi, '-').slice(0, 80)
}

/**
 * The evidence drawer: confidence, measured facts with citations and
 * provenance, the tool trace, the sources, and the raw JSON download.
 */
export function EvidencePanel({
  evidence,
  sources,
  latencyMs,
  runId,
  question,
  answer,
  agentId,
  agentName,
  className,
}: EvidencePanelProps) {
  const toast = useToast()
  const facts = useMemo(() => normalizeFacts(evidence?.facts), [evidence])
  const trace = useMemo(() => normalizeTrace(evidence?.trace), [evidence])
  const evidenceSources = useMemo(() => {
    if (Array.isArray(evidence?.sources) && evidence.sources.length > 0) return evidence.sources
    return sources ?? []
  }, [evidence, sources])

  const measuredCount = facts.filter((fact) => isMeasured(fact.provenance)).length
  const citationCount = facts.filter((fact) => Boolean(fact.citation)).length
  const hasEvidence = Boolean(evidence) || facts.length > 0 || trace.length > 0
  const relationships = useMemo(
    () => normalizeFacts(evidence?.relationships),
    [evidence],
  )
  const sourceRecords = useMemo(
    () => (evidence?.source_records ?? []).slice(0, 3),
    [evidence],
  )
  const priorEvidence = useMemo(
    () => (evidence?.prior_evidence ?? []).slice(0, 4),
    [evidence],
  )
  const lineage = evidence?.lineage

  const handleDownload = () => {
    const record = buildEvidenceRecord({
      agentId,
      agentName,
      runId: runId ?? 'unpublished-run',
      question,
      answer,
      evidence,
      sources: evidenceSources,
      latencyMs: latencyMs ?? null,
      trace,
      facts,
    })
    const suffix = safeFilename(runId ?? String(Date.now()))
    downloadJson(`evidence-${safeFilename(agentId)}-${suffix}.json`, record)
    toast.push({
      tone: 'success',
      title: 'Evidence JSON downloaded',
      message: `${facts.length} facts and ${trace.length} trace steps.`,
    })
  }

  return (
    <Card
      title="Evidence"
      subtitle="Every claim, where it came from, and what the agent did to get it."
      className={cx('evidence-panel', className)}
      actions={
        <Button
          variant="secondary"
          size="sm"
          icon={<Download size={14} aria-hidden="true" />}
          onClick={handleDownload}
          disabled={!hasEvidence}
        >
          Download JSON
        </Button>
      }
    >
      {!hasEvidence ? (
        <EmptyState
          icon={FileJson}
          title="No evidence yet"
          description="Ask a question and this panel fills with the trace, the cited facts and the confidence behind the answer."
          compact
        />
      ) : (
        <div className="evidence">
          <div className="evidence__summary">
            <div className="evidence__confidence">
              <div className="evidence__confidence-head">
                <span className="evidence__label">Confidence</span>
              </div>
              <ConfidenceMeter value={evidence?.confidence} />
            </div>
            <div className="evidence__counters">
              <div className="evidence__counter">
                <span className="evidence__label">Latency</span>
                <strong>{formatLatency(latencyMs ?? undefined)}</strong>
              </div>
              <div className="evidence__counter">
                <span className="evidence__label">Facts</span>
                <strong>
                  {facts.length}
                  <span className="evidence__subtle"> · {measuredCount} measured</span>
                </strong>
              </div>
              <div className="evidence__counter">
                <span className="evidence__label">Citations</span>
                <strong>{citationCount}</strong>
              </div>
            </div>
          </div>

          <section className="evidence__section" aria-label="Trace steps">
            <h3 className="evidence__section-title">
              <GitBranch size={14} aria-hidden="true" />
              Trace
              <Badge tone="neutral">{trace.length}</Badge>
            </h3>
            {trace.length === 0 ? (
              <p className="evidence__empty-line">This answer returned no tool trace.</p>
            ) : (
              <ol className="trace">
                {trace.map((step, index) => (
                  <li className="trace__step" key={`${step.tool}-${index}`}>
                    <span className="trace__index" aria-hidden="true">
                      {index + 1}
                    </span>
                    <div className="trace__body">
                      <div className="trace__head">
                        <code className="trace__tool">{step.tool}</code>
                        {step.latencyMs !== null ? (
                          <span className="trace__latency">{formatLatency(step.latencyMs)}</span>
                        ) : null}
                      </div>
                      <dl className="trace__io">
                        <div className="trace__io-row">
                          <dt>Args</dt>
                          <dd title={step.argsSummary}>{step.argsSummary}</dd>
                        </div>
                        <div className="trace__io-row">
                          <dt>Result</dt>
                          <dd title={step.resultSummary}>{step.resultSummary}</dd>
                        </div>
                      </dl>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="evidence__section" aria-label="Measured facts">
            <h3 className="evidence__section-title">
              <FileJson size={14} aria-hidden="true" />
              Facts
              <Badge tone={measuredCount > 0 ? 'teal' : 'neutral'}>
                {measuredCount > 0 ? `${measuredCount} measured` : 'none measured'}
              </Badge>
            </h3>
            {facts.length === 0 ? (
              <p className="evidence__empty-line">This answer returned no facts.</p>
            ) : (
              <ul className="fact-list">
                {facts.map((fact, index) => (
                  <li className="fact" key={`${fact.citation}-${index}`}>
                    <div className="fact__head">
                      <ProvenanceBadge provenance={fact.provenance} />
                      {fact.citation ? (
                        <code className="fact__citation" title={`Citation: ${fact.citation}`}>
                          {fact.citation}
                        </code>
                      ) : (
                        <span className="fact__no-citation">no citation</span>
                      )}
                    </div>
                    <p className="fact__text">{fact.text}</p>
                    {fact.asOf ? (
                      <p className="fact__as-of">As of {formatAsOf(fact.asOf)}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {priorEvidence.length > 0 ? (
            <section className="evidence__section" aria-label="Prior period evidence">
              <h3 className="evidence__section-title">
                <GitBranch size={14} aria-hidden="true" />
                Prior period
                <Badge tone="neutral">{priorEvidence.length}</Badge>
              </h3>
              <div className="prior-grid">
                {priorEvidence.map((item) => (
                  <div className="prior-card" key={`${item.metric}-${item.prior_window?.from ?? ''}`}>
                    <span className="evidence__label">{item.title || item.metric}</span>
                    <p className="prior-card__values">
                      <span>{formatValue(item.prior)}</span>
                      <span aria-hidden="true">→</span>
                      <strong>{formatValue(item.current)}</strong>
                    </p>
                    <p className="evidence__subtle">
                      {item.change_pct !== null && item.change_pct !== undefined
                        ? `${item.change_pct >= 0 ? '+' : ''}${formatNumber(item.change_pct)}%`
                        : 'No comparable change'}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {relationships.length > 0 ? (
            <section className="evidence__section" aria-label="Relationships">
              <h3 className="evidence__section-title">
                <GitBranch size={14} aria-hidden="true" />
                Relationships
                <Badge tone="neutral">{relationships.length}</Badge>
              </h3>
              <ul className="relationship-list">
                {relationships.slice(0, 12).map((fact, index) => (
                  <li className="relationship" key={`${fact.citation}-${index}`}>
                    <span>{fact.text}</span>
                    {fact.citation ? <code>{fact.citation}</code> : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {sourceRecords.length > 0 ? (
            <section className="evidence__section" aria-label="Source records">
              <h3 className="evidence__section-title">
                <FileJson size={14} aria-hidden="true" />
                Source records
                <Badge tone="neutral">{sourceRecords.length}</Badge>
              </h3>
              <div className="source-record-list">
                {sourceRecords.map((record, index) => (
                  <div className="source-record" key={`${record.table}-${index}`}>
                    <div className="source-record__head">
                      <code>{record.table}</code>
                      <span>{record.rows?.length ?? 0} sample rows</span>
                    </div>
                    <div className="source-record__table">
                      {(record.rows ?? []).slice(0, 3).map((row, rowIndex) => (
                        <div className="source-record__row" key={rowIndex}>
                          {(record.columns ?? []).slice(0, 7).map((column) => (
                            <span key={column} className="source-record__cell">
                              <span className="evidence__label">{column}</span>
                              {formatValue(row[column])}
                            </span>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {lineage && ((lineage.definitions?.length ?? 0) > 0 || (lineage.sql?.length ?? 0) > 0) ? (
            <section className="evidence__section" aria-label="Metric lineage">
              <h3 className="evidence__section-title">
                <Link2 size={14} aria-hidden="true" />
                Metric lineage
              </h3>
              {(lineage.sql ?? []).length > 0 ? (
                <details className="lineage">
                  <summary>{lineage.sql?.length} compiled statement(s)</summary>
                  <pre className="code-block">{lineage.sql?.join('\n\n')}</pre>
                </details>
              ) : null}
              {(lineage.definitions ?? []).map((item) => (
                <div className="lineage__definition" key={item.metric}>
                  <code>{item.metric}</code>
                  <span>{String((item.definition as { description?: unknown })?.description ?? '')}</span>
                </div>
              ))}
            </section>
          ) : null}

          <section className="evidence__section" aria-label="Sources">
            <h3 className="evidence__section-title">
              <Link2 size={14} aria-hidden="true" />
              Sources
            </h3>
            {evidenceSources.length === 0 ? (
              <p className="evidence__empty-line">No source was attached to this answer.</p>
            ) : (
              <div className="chip-row">
                {evidenceSources.map((source) => (
                  <Badge key={source} tone="indigo" title={source}>
                    {humanize(source)}
                  </Badge>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </Card>
  )
}
