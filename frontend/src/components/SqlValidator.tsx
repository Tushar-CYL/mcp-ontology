import { useState } from 'react'
import { Bot, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'
import type { ValidationResult } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { validationTone } from '../utils/governance'
import { Badge } from './Badge'
import { Button } from './Button'
import { Callout } from './Callout'
import { Card } from './Card'
import { ErrorState } from './ErrorState'
import { TextArea } from './Field'

const EXAMPLE = 'SELECT SUM(line_revenue) FROM order_lines'

/**
 * Phase 5 on the analyst's screen: paste SQL an agent (or a person) wrote and
 * see whether it computes the certified metric. The same check is the MCP
 * tool `validate_sql`, so the analyst sees exactly what agents are told.
 */
export function SqlValidator({ source, metric }: { source: string; metric: string }) {
  const [sql, setSql] = useState(EXAMPLE)
  const [result, setResult] = useState<ValidationResult | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.validateSql({ source, metric, sql }))
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title="Check agent SQL"
      subtitle={`Does this SQL compute certified ${metric}? Agents run the same check with validate_sql. Nothing is executed.`}
      actions={result ? <Badge tone={validationTone(result.status)} dot>{result.status}</Badge> : null}
    >
      <TextArea label="SQL" rows={3} value={sql} onChange={(e) => setSql(e.target.value)} className="mono" />
      {error ? <ErrorState error={error} compact /> : null}
      <div className="form-actions">
        <Button
          variant="primary"
          icon={<ShieldCheck size={15} aria-hidden="true" />}
          loading={busy}
          disabled={!sql.trim()}
          onClick={() => void run()}
        >
          Validate
        </Button>
      </div>
      {result ? (
        <>
          <div className="metric-health">
            {result.checks.map((check) => (
              <div
                key={check.name}
                className={check.passed ? 'metric-check metric-check--pass' : 'metric-check metric-check--fail'}
              >
                <span className="metric-check__dot" aria-hidden="true" />
                <div>
                  <p className="metric-check__name">{check.name}</p>
                  <p className="metric-check__detail">{check.detail}</p>
                </div>
              </div>
            ))}
          </div>
          {result.suggestion ? (
            <Callout tone={result.status === 'fail' ? 'danger' : 'warning'} title="Use the certified number">
              {result.suggestion}
            </Callout>
          ) : null}
        </>
      ) : null}
    </Card>
  )
}

/** Phase 6: how much agents actually consume this metric. */
export function MetricUsageBadge({ source, metric }: { source: string; metric: string }) {
  const usage = useAsync((signal) => api.metricUsage(source, signal), [source])
  const row = usage.data?.metrics.find((m) => m.metric === metric)
  if (!usage.data) return null
  return (
    <Badge tone={row ? 'indigo' : 'neutral'} icon={<Bot size={13} aria-hidden="true" />}>
      {row ? `${row.calls} agent call(s) · ${row.agents} agent(s)` : 'Not used by agents yet'}
    </Badge>
  )
}
