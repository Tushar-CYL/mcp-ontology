import { useState } from 'react'
import { Database, FileText, Plus, Sparkles, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { EoJob, OntoAi } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { TextInput } from '../../components/Field'
import { useSource } from '../../context/SourceContext'
import { JobLog } from './shared'

/**
 * Screen 1: connect. Pick data that is already connected or point at a new
 * file / folder / database, optionally add the metadata the client already
 * has (Power BI model, dbt file, data dictionary), and build.
 */
export function Connect({ ai, onBuilt }: { ai: OntoAi | undefined; onBuilt: (oid: string) => void }) {
  const { sources, refresh } = useSource()
  const [name, setName] = useState('')
  const [domain, setDomain] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [paths, setPaths] = useState<string[]>([])
  const [pathDraft, setPathDraft] = useState('')
  const [metadata, setMetadata] = useState<string[]>([])
  const [metaDraft, setMetaDraft] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)

  const toggle = (id: string) =>
    setPicked((now) => (now.includes(id) ? now.filter((x) => x !== id) : [...now, id]))
  const addPath = () => {
    const p = pathDraft.trim().replace(/^"|"$/g, '')
    if (p && !paths.includes(p)) setPaths([...paths, p])
    setPathDraft('')
  }
  const addMeta = () => {
    const p = metaDraft.trim().replace(/^"|"$/g, '')
    if (p && !metadata.includes(p)) setMetadata([...metadata, p])
    setMetaDraft('')
  }
  const nothing = !picked.length && !paths.length && !metadata.length
  const build = async () => {
    setError(null)
    setStarting(true)
    try {
      const out = await api.ontoBuild({
        name: name.trim() || 'My ontology', sources: picked,
        paths: paths.map((path) => ({ path })), metadata, domain: domain.trim(),
      })
      setJobId(out.job_id)
    } catch (e) {
      setError(describeError(e).message)
    } finally {
      setStarting(false)
    }
  }
  const finished = (job: EoJob) => {
    setJobId(null)
    if (job.status === 'done' && job.result && typeof job.result.ontology === 'string') {
      void refresh()
      onBuilt(job.result.ontology)
    } else {
      setError(job.error ?? 'The build failed.')
    }
  }

  if (jobId) {
    return (
      <Card title="Building your ontology"
        subtitle="Profiling every column, finding the business things, proving the links, then writing plain meanings and checking each one against the data.">
        <JobLog jobId={jobId} onFinished={finished} />
      </Card>
    )
  }

  return (
    <div className="onto-connect">
      <Card title="Your data" subtitle="Any data: a CSV or Excel file, a folder of files, a database file, or a database URL.">
        {sources.length ? (
          <div className="onto-sources" role="group" aria-label="Connected sources">
            {sources.map((s) => (
              <label key={s.id} className={`onto-source${picked.includes(s.id) ? ' is-picked' : ''}`}>
                <input type="checkbox" checked={picked.includes(s.id)} onChange={() => toggle(s.id)} />
                <Database size={16} aria-hidden="true" />
                <span className="onto-source__name">{s.name || s.id}</span>
                <span className="muted">{s.tables} tables</span>
              </label>
            ))}
          </div>
        ) : <p className="muted">Nothing connected yet. Add a path below.</p>}
        <div className="onto-add">
          <TextInput label="Add a file, folder or database" value={pathDraft}
            placeholder="D:\data\sales.csv   or   D:\data\shop\   or   postgres://user@host/db"
            onChange={(e) => setPathDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') addPath() }} />
          <Button icon={<Plus size={15} />} onClick={addPath} disabled={!pathDraft.trim()}>Add</Button>
        </div>
        <Chips items={paths} onRemove={(p) => setPaths(paths.filter((x) => x !== p))} />
      </Card>

      <Card title="Metadata you already have (optional)"
        subtitle="A Power BI / Fabric semantic model (.bim), a dbt file (schema.yml) or a data dictionary (.csv / .xlsx with table, column, description). Its descriptions win over the AI. A semantic model alone is enough to start.">
        <div className="onto-add">
          <TextInput label="Metadata file" value={metaDraft}
            placeholder="D:\models\model.bim   or   D:\dbt\models\schema.yml   or   D:\dictionary.csv"
            onChange={(e) => setMetaDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') addMeta() }} />
          <Button icon={<FileText size={15} />} onClick={addMeta} disabled={!metaDraft.trim()}>Add</Button>
        </div>
        <Chips items={metadata} onRemove={(p) => setMetadata(metadata.filter((x) => x !== p))} />
      </Card>

      <Card title="Name it">
        <div className="onto-name">
          <TextInput label="Ontology name" value={name} placeholder="e.g. Plant sensors"
            onChange={(e) => setName(e.target.value)} />
          <TextInput label="What is this data about? (optional)" value={domain}
            placeholder="e.g. hospital visits, factory IoT, retail orders"
            hint="A few words help the AI choose the right business names."
            onChange={(e) => setDomain(e.target.value)} />
        </div>
        <AiLine ai={ai} />
        {error ? <Callout tone="danger" title="Could not build">{error}</Callout> : null}
        <div className="onto-actions">
          <Button variant="primary" icon={<Sparkles size={16} />} onClick={build}
            loading={starting} disabled={nothing}>Build ontology</Button>
          {nothing ? <span className="muted">Pick or add data, or add a semantic model.</span> : null}
        </div>
      </Card>
    </div>
  )
}

function Chips({ items, onRemove }: { items: string[]; onRemove: (item: string) => void }) {
  if (!items.length) return null
  return (
    <ul className="onto-chips">
      {items.map((item) => (
        <li key={item} className="onto-chip">
          <span className="code">{item}</span>
          <button type="button" aria-label={`Remove ${item}`} onClick={() => onRemove(item)}>
            <X size={14} />
          </button>
        </li>
      ))}
    </ul>
  )
}

export function AiLine({ ai }: { ai: OntoAi | undefined }) {
  if (!ai) return null
  return ai.configured ? (
    <p className="onto-ai">
      <Badge tone="teal" dot>AI on</Badge>
      <span>AI writes the names and meanings, and the data checks every one. It sees column names and
        {ai.samples_per_column ? ` ${ai.samples_per_column} sample values per column` : ' no sample values'}, never whole tables.</span>
    </p>
  ) : (
    <p className="onto-ai">
      <Badge tone="slate" dot>AI off</Badge>
      <span>Names come from the column names and the data. Everything still works; meanings are simpler.</span>
    </p>
  )
}
