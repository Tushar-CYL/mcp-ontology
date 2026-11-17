import { useMemo, useState } from 'react'
import { Save, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { OntoAgent, OntoAgentBody, OntoAgentKind, OntoAgentsList } from '../../api/types'
import { Button } from '../../components/Button'
import { useToast } from '../../context/ToastContext'
import { AskBox } from './AgentPanel'
import { KIND_HELP, KIND_ICON } from './kinds'

/**
 * Create an agent, or change one of yours. "Start from" fills the form from a
 * built-in (or another of yours); everything is checked against the ontology
 * on save, and "Try it" asks the agent as written before anything is saved.
 */
export function AgentForm({ oid, list, editing, onSaved, onCancel }: {
  oid: string
  list: OntoAgentsList
  editing: OntoAgent | null
  onSaved: (a: OntoAgent) => void
  onCancel: () => void
}) {
  const toast = useToast()
  const all = useMemo(() => [...list.builtin, ...list.mine], [list])
  const [name, setName] = useState(editing?.name ?? '')
  const [kind, setKind] = useState<OntoAgentKind>(editing?.kind ?? 'insight')
  const [job, setJob] = useState(editing?.job ?? '')
  const [instructions, setInstructions] = useState(editing?.instructions ?? '')
  const [things, setThings] = useState<string[]>(editing?.scope.things ?? [])
  const [metrics, setMetrics] = useState<string[]>(editing?.scope.metrics ?? [])
  const [examples, setExamples] = useState<string>((editing?.examples ?? []).map((e) => e.text).join('\n'))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startFrom = (id: string) => {
    const a = all.find((x) => x.id === id)
    if (!a) return
    setKind(a.kind)
    setJob(a.job)
    setInstructions(a.instructions)
    setThings(a.scope.things)
    setMetrics(a.scope.metrics)
    setExamples(a.examples.map((e) => e.text).join('\n'))
    if (!name.trim()) setName(`My ${a.name}`)
  }
  const body = (): OntoAgentBody => ({
    name: name.trim(), kind, job: job.trim(), instructions: instructions.trim(),
    scope: { things, metrics },
    examples: examples.split('\n').map((x) => x.trim()).filter(Boolean),
  })
  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const saved = editing ? await api.updateOntoAgent(editing.id, body()) : await api.createOntoAgent(oid, body())
      toast.push({ tone: 'success', title: editing ? 'Saved' : 'Agent created', message: saved.name })
      onSaved(saved)
    } catch (e) {
      setError(describeError(e).message)
    } finally {
      setSaving(false)
    }
  }
  const toggle = (list_: string[], set: (v: string[]) => void, v: string) =>
    set(list_.includes(v) ? list_.filter((x) => x !== v) : [...list_, v])
  const usesMetrics = kind === 'metric' || kind === 'insight' || kind === 'trust'

  return (
    <section className="ag-form" aria-label={editing ? 'Change agent' : 'Create an agent'}>
      <header className="ag-form__head">
        <h2>{editing ? `Change ${editing.name}` : 'Create an agent'}</h2>
        <button type="button" aria-label="Close" onClick={onCancel}><X size={16} /></button>
      </header>
      {!editing ? (
        <label className="ag-field">
          <span>Start from</span>
          <select className="input" defaultValue="" onChange={(e) => startFrom(e.target.value)}>
            <option value="">Blank</option>
            {all.map((a) => <option key={a.id} value={a.id}>{a.builtin ? '' : 'Mine: '}{a.name}</option>)}
          </select>
        </label>
      ) : null}
      <label className="ag-field">
        <span>Name</span>
        <input className="input" value={name} maxLength={80} placeholder="e.g. Cancelled orders watcher"
          onChange={(e) => setName(e.target.value)} />
      </label>
      <fieldset className="ag-field">
        <legend>How it answers</legend>
        <div className="ag-kinds">
          {list.kinds.map((k) => {
            const Icon = KIND_ICON[k.kind]
            return (
              <label key={k.kind} className={`ag-kind${kind === k.kind ? ' is-picked' : ''}`}>
                <input type="radio" name="kind" checked={kind === k.kind} onChange={() => setKind(k.kind)} />
                <Icon size={16} aria-hidden="true" />
                <b>{k.title}</b>
                <small>{KIND_HELP[k.kind]}</small>
              </label>
            )
          })}
        </div>
      </fieldset>
      <fieldset className="ag-field">
        <legend>What it may use <small>(none ticked = everything)</small></legend>
        <div className="ag-checks">
          {list.things.map((t) => (
            <label key={t}><input type="checkbox" checked={things.includes(t)} onChange={() => toggle(things, setThings, t)} /> {t}</label>
          ))}
        </div>
        {usesMetrics && list.metrics.length ? (
          <>
            <p className="muted">Metrics</p>
            <div className="ag-checks">
              {list.metrics.map((m) => (
                <label key={m.name}><input type="checkbox" checked={metrics.includes(m.name)}
                  onChange={() => toggle(metrics, setMetrics, m.name)} /> {m.title}{m.certified ? ' ✓' : ' (proposed)'}</label>
              ))}
            </div>
          </>
        ) : null}
      </fieldset>
      <label className="ag-field">
        <span>What it is for</span>
        <input className="input" value={job} maxLength={300} placeholder="One sentence people will read on its card"
          onChange={(e) => setJob(e.target.value)} />
      </label>
      <label className="ag-field">
        <span>How it should answer <small>(style only: it can never use anything outside its scope)</small></span>
        <textarea className="input" rows={2} value={instructions} maxLength={2000}
          placeholder="e.g. Answer in one sentence and give the number first."
          onChange={(e) => setInstructions(e.target.value)} />
      </label>
      <label className="ag-field">
        <span>Example questions <small>(one per line)</small></span>
        <textarea className="input" rows={3} value={examples} onChange={(e) => setExamples(e.target.value)} />
      </label>
      {error ? <p className="kgb__error">{error}</p> : null}
      <div className="ag-form__try">
        <p className="muted">Try it before saving:</p>
        <AskBox examples={examples.split('\n').filter(Boolean).slice(0, 3).map((t) => ({ text: t }))}
          onAsk={(q) => api.tryOntoAgent(oid, { ...body(), name: body().name || 'Draft', question: q })} />
      </div>
      <div className="ag-form__actions">
        <Button variant="primary" icon={<Save size={15} />} loading={saving} disabled={!name.trim()} onClick={() => void save()}>
          {editing ? 'Save changes' : 'Create agent'}
        </Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </section>
  )
}
