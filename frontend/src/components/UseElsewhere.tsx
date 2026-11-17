import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Download, FileJson, PackageOpen, Plug, Upload } from 'lucide-react'
import { api, describeError } from '../api/client'
import { Button } from './Button'
import { CopyLine } from './CopyLine'
import { DownloadLink } from './DownloadLink'

export type LayerId = 'ontology' | 'graph' | 'semantic' | 'context'

type Format = { label: string; note: string; href: string }

const NAMES: Record<LayerId, string> = {
  ontology: 'Ontology', graph: 'Knowledge graph', semantic: 'Semantic', context: 'Context',
}

function enc(oid: string) {
  return encodeURIComponent(oid)
}

function formats(layer: LayerId, oid: string): Format[] {
  const o = enc(oid)
  switch (layer) {
    case 'ontology':
      return [
        { label: 'Strata Model (JSON)', note: 'Open format: import it in any Strata, or read it in your own code', href: `/api/onto/${o}/contract` },
        { label: 'Apache Ossie (YAML)', note: 'Semantic-layer interchange', href: `/api/onto/${o}/ossie` },
        { label: 'OWL / Turtle', note: 'Standard ontology format', href: `/api/eo/${o}/export/turtle` },
        { label: 'Excel', note: 'Things, fields and links as sheets', href: `/api/onto/${o}/excel` },
      ]
    case 'graph':
      return [
        { label: 'RDF (N-Triples)', note: 'Any triple store: GraphDB, Stardog, Neptune, Jena', href: `/api/kg/${o}/rdf` },
        { label: 'JSON nodes and edges', note: 'Cytoscape, D3, NetworkX', href: `/api/kg/${o}/graph.json` },
        { label: 'Neo4j import files', note: 'neo4j-admin database import', href: `/api/kg/${o}/neo4j` },
      ]
    case 'semantic':
      return [
        { label: 'SQL views', note: 'One CREATE VIEW per certified metric, over your own tables', href: `/api/sem/${o}/export?format=sql` },
        { label: 'dbt MetricFlow (YAML)', note: 'Semantic models and certified metrics for dbt', href: `/api/sem/${o}/export?format=metricflow` },
        { label: 'SQL views, proposed too', note: 'Every metric, certified or not', href: `/api/sem/${o}/export?format=sql&status=all` },
      ]
    case 'context':
      return []
  }
}

const TOOLS: Record<LayerId, string> = {
  ontology: 'get_ontology',
  graph: 'find_entity, get_entity, how_connected',
  semantic: 'list_business_metrics, get_business_metric',
  context: 'context_for_question',
}

function cli(layer: LayerId, oid: string): string {
  switch (layer) {
    case 'ontology': return `strata export ontology ${oid} -o ${oid}.strata-model.json`
    case 'graph': return `strata export graph ${oid} --format rdf -o ${oid}.nt`
    case 'semantic': return `strata export semantic ${oid} --format metricflow -o metrics.yml`
    case 'context': return `strata context ${oid} "your question"`
  }
}

function api_(layer: LayerId, oid: string): string {
  const o = enc(oid)
  switch (layer) {
    case 'ontology': return `GET /api/onto/${o}`
    case 'graph': return `GET /api/kg/${o}/search?q=...`
    case 'semantic': return `GET /api/sem/${o}`
    case 'context': return `POST /api/ctx/${o}/pack  {"question": "..."}`
  }
}

/**
 * How to use one layer outside this app, in three ways: download it in an
 * open format, run only this layer as a ready-made copy, or call it from
 * your own tools. Plus: bring your own ontology instead of ours.
 */
export function UseElsewhere({ layer, oid, open = false }: { layer: LayerId; oid: string; open?: boolean }) {
  const name = NAMES[layer]
  const zipLayers = layer === 'ontology' ? 'ontology' : layer
  const bundle = `/api/bundle?layers=${zipLayers}&ontology=${enc(oid)}`
  const mcp = `${window.location.origin}/mcp`
  return (
    <details className="use-x" open={open}>
      <summary>
        <PackageOpen size={17} aria-hidden="true" />
        <span>Use the {name} layer in your own system</span>
        <small>download it, run only this layer, or call it from your tools</small>
      </summary>
      <div className="use-x__grid">
        <section className="use-x__col">
          <h4><Download size={15} aria-hidden="true" /> 1. Download it</h4>
          {layer === 'context' ? <PackForm oid={oid} /> : (
            <ul className="use-x__files">
              {formats(layer, oid).map((f) => (
                <li key={f.href}>
                  <DownloadLink href={f.href} fallback={`${oid}-${layer}`}><FileJson size={14} aria-hidden="true" /> {f.label}</DownloadLink>
                  <span>{f.note}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="use-x__col">
          <h4><PackageOpen size={15} aria-hidden="true" /> 2. Run only this layer</h4>
          <p>A ready-to-run copy with only the {name} layer and this ontology as the starting point. Python only, no Docker.</p>
          <DownloadLink className="btn btn--primary btn--sm use-x__zip" href={bundle} fallback={`strata-${layer}.zip`}>
            <Download size={14} aria-hidden="true" /> Download ready-to-run zip
          </DownloadLink>
          <ol className="use-x__steps">
            <li>Unzip it on the other machine.</li>
            <li>Double-click <code>start.bat</code> (Mac / Linux: <code>./start.sh</code>).</li>
            <li>Open <code>http://127.0.0.1:8000</code> and connect your own data.</li>
          </ol>
        </section>
        <section className="use-x__col">
          <h4><Plug size={15} aria-hidden="true" /> 3. Call it from your tools</h4>
          <CopyLine label="API" value={api_(layer, oid)} />
          <CopyLine label="MCP" value={`${mcp}  ·  ${TOOLS[layer]}`} />
          <CopyLine label="Command line" value={cli(layer, oid)} />
        </section>
      </div>
      <p className="use-x__own">
        <Upload size={14} aria-hidden="true" /> Have your own ontology? Use it with this layer:{' '}
        <Link to="/tools/ontology/new?mode=model">Ontology → New → Use my ontology exactly <ArrowRight size={13} aria-hidden="true" /></Link>
      </p>
    </details>
  )
}

/** Context has no fixed file: the pack is made for one question. */
function PackForm({ oid }: { oid: string }) {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const get = async () => {
    setBusy(true)
    setError(null)
    try {
      const pack = await api.ctxPack(oid, q.trim())
      const blob = new Blob([JSON.stringify(pack, null, 2)], { type: 'application/json' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `${oid}-context-pack.json`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (e) {
      setError(describeError(e).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="use-x__pack" onSubmit={(e) => { e.preventDefault(); void get() }}>
      <p>The Context Pack: the checked facts for one question, each with its source. Any AI can answer from it.</p>
      <input className="input" value={q} maxLength={1000} aria-label="Question for the Context Pack"
        placeholder="A question, e.g. revenue by payment type" onChange={(e) => setQ(e.target.value)} />
      <Button type="submit" size="sm" loading={busy} disabled={!q.trim()} icon={<FileJson size={14} />}>Get Context Pack (JSON)</Button>
      {error ? <p className="kgb__error">{error}</p> : null}
    </form>
  )
}
