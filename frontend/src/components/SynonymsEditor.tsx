import { useState } from 'react'
import { Tags } from 'lucide-react'
import { api } from '../api/client'
import { useToast } from '../context/ToastContext'
import { parseList } from '../utils/governance'
import { Badge } from './Badge'
import { Button } from './Button'
import { Card } from './Card'
import { ErrorState } from './ErrorState'
import { TextInput } from './Field'

/**
 * The words people use for a metric. "sales" then finds Revenue for every
 * agent, and a word can belong to one metric only, so it never becomes
 * ambiguous. Snowflake, Databricks and dbt attach synonyms the same way.
 */
export function SynonymsEditor({
  source,
  metric,
  synonyms,
  onSaved,
}: {
  source: string
  metric: string
  synonyms: string[]
  onSaved: () => void
}) {
  const toast = useToast()
  const [text, setText] = useState(synonyms.join(', '))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      const saved = await api.setMetricSynonyms(metric, source, parseList(text))
      setText(saved.synonyms.join(', '))
      toast.push({ tone: 'success', title: 'Synonyms saved', message: saved.synonyms.join(', ') || 'none' })
      onSaved()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title="Words people use"
      subtitle="Synonyms let agents find this metric by everyday words. A word can mean one metric only."
      actions={<Tags size={16} aria-hidden="true" />}
    >
      <div className="chip-row synonyms-current">
        {synonyms.length ? synonyms.map((s) => <Badge key={s} tone="neutral">{s}</Badge>)
          : <span className="muted">No synonyms yet.</span>}
      </div>
      <TextInput
        label="Synonyms"
        value={text}
        placeholder="sales, turnover"
        hint="Comma-separated. Saving replaces the list."
        onChange={(event) => setText(event.target.value)}
      />
      {error ? <ErrorState error={error} compact /> : null}
      <div className="form-actions">
        <Button variant="primary" loading={busy} onClick={() => void save()}>
          Save synonyms
        </Button>
      </div>
    </Card>
  )
}
