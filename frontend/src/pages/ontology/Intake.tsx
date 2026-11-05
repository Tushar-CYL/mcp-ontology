import { useState } from 'react'
import { Database, PlayCircle } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { EoRole, EoSource } from '../../api/types'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { Select, TextArea, TextInput } from '../../components/Field'
import { useSource } from '../../context/SourceContext'
import { useToast } from '../../context/ToastContext'
import { ROLE_LABEL } from '../../utils/eo'
import { JobLog } from './shared'

const ROLES = Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }))

/**
 * Step 1, Intake: the problem first, then each source's role, owner and
 * refresh SLA. Or load the BI/MDM demo that reproduces the team's problem.
 */
export function Intake({ onCreated }: { onCreated: (oid: string) => void }) {
  const toast = useToast()
  const { sources, refresh } = useSource()
  const [jobId, setJobId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [form, setForm] = useState({ id: '', name: '', problem: '', domain: '', questions: '' })
  const [picked, setPicked] = useState<Record<string, EoSource>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startDemo = async () => {
    setStarting(true)
    try {
      setJobId((await api.eoDemo(300)).job_id)
    } catch (cause) {
      toast.push({ title: 'Could not start the demo', message: describeError(cause).message, tone: 'error' })
    } finally {
      setStarting(false)
    }
  }

  const toggle = (sourceId: string) => setPicked((current) => {
    const next = { ...current }
    if (next[sourceId]) delete next[sourceId]
    else next[sourceId] = { source_id: sourceId, role: 'source_system', owner_team: '', cadence_days: 1 }
    return next
  })
  const edit = (sourceId: string, patch: Partial<EoSource>) =>
    setPicked((current) => ({ ...current, [sourceId]: { ...current[sourceId], ...patch } }))

  const create = async () => {
    setError(null)
    if (!form.id.trim() || !form.name.trim()) return setError('Give the ontology an id and a name.')
    if (!Object.keys(picked).length) return setError('Pick at least one loaded source.')
    setSaving(true)
    try {
      await api.eoCreate({
        id: form.id.trim(), name: form.name.trim(), problem: form.problem.trim(),
        domain: form.domain.trim(),
        questions: form.questions.split('\n').map((q) => q.trim()).filter(Boolean),
        sources: Object.values(picked),
      })
      onCreated(form.id.trim())
    } catch (cause) {
      setError(describeError(cause).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid-2 grid-2--wide-left">
      <Card title="Start from your sources" subtitle="State the problem first: every suggestion is judged against it.">
        <div className="stack">
          <TextInput label="Ontology id" placeholder="sales" value={form.id}
            onChange={(e) => setForm({ ...form, id: e.target.value })} />
          <TextInput label="Name" placeholder="Sales reporting" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <TextArea label="Problem statement" rows={3} value={form.problem}
            placeholder="Monthly sales reports are late and disagree with finance..."
            onChange={(e) => setForm({ ...form, problem: e.target.value })} />
          <TextInput label="Domain" placeholder="Sales / order-to-cash" value={form.domain}
            onChange={(e) => setForm({ ...form, domain: e.target.value })} />
          <TextArea label="Business questions (one per line)" rows={3} value={form.questions}
            onChange={(e) => setForm({ ...form, questions: e.target.value })} />
          <div>
            <p className="field__label">Sources, with their role, owner team and refresh SLA</p>
            {sources.length === 0 ? (
              <p className="muted">No sources are loaded yet. Load them under Data sources, or start the demo.</p>
            ) : (
              <ul className="eo-source-picker">
                {sources.map((s) => {
                  const chosen = picked[s.id]
                  return (
                    <li key={s.id}>
                      <label className="cell-inline">
                        <input type="checkbox" checked={Boolean(chosen)} onChange={() => toggle(s.id)} />
                        <span className="cell-title">{s.id}</span>
                      </label>
                      {chosen ? (
                        <div className="eo-source-picker__fields">
                          <Select label="Role" value={chosen.role} options={ROLES}
                            onValueChange={(v) => edit(s.id, { role: v as EoRole })} />
                          <TextInput label="Owner team" value={chosen.owner_team}
                            onChange={(e) => edit(s.id, { owner_team: e.target.value })} />
                          <TextInput label="Refresh SLA (days)" type="number" min={1}
                            value={chosen.cadence_days}
                            onChange={(e) => edit(s.id, { cadence_days: Math.max(1, Number(e.target.value) || 1) })} />
                        </div>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
          {error ? <Callout tone="danger">{error}</Callout> : null}
          <div className="form-actions">
            <Button variant="primary" icon={<Database size={15} />} loading={saving} onClick={create}>
              Create ontology
            </Button>
          </div>
        </div>
      </Card>
      <Card title="Or see it on the BI/MDM problem" subtitle="Generated data with a known answer key.">
        <div className="stack">
          <p>
            CRM, ERP and billing hold customers under different ids. An MDM hub masters them but runs
            two to three weeks behind and holds corrections the sources never got. The data mart's
            "revenue" is built from one of ten amount columns. Which one?
          </p>
          <ul className="eo-list">
            <li>5 sources: CRM, ERP, billing, MDM hub, data mart</li>
            <li>10 amount columns with SAP names (NETWR, MWSBK, BRTWR ...)</li>
            <li>planted duplicates, corrections, stale data and rule violations</li>
          </ul>
          {jobId ? (
            <JobLog jobId={jobId} onFinished={(job) => {
              if (job.status === 'done') {
                void refresh()
                onCreated(String(job.result?.ontology ?? 'sales'))
              }
              else setJobId(null)
            }} />
          ) : (
            <Button variant="primary" icon={<PlayCircle size={15} />} loading={starting} onClick={startDemo}>
              Load the demo and run the accelerator
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}
