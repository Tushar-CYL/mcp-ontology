import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Download, PackageOpen, Plus } from 'lucide-react'
import { api } from '../api/client'
import { Button } from '../components/Button'
import { DownloadLink } from '../components/DownloadLink'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { UseElsewhere, type LayerId } from '../components/UseElsewhere'
import { useSource } from '../context/SourceContext'
import { useAsync } from '../hooks/useAsync'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

const ALL: LayerId[] = ['ontology', 'graph', 'semantic', 'context']

/**
 * Every way to use Strata's layers: all four here, your own ontology under
 * our layers, or any one layer taken to your own system.
 */
export function UseAnywhere() {
  useDocumentTitle('Use anywhere')
  const { health } = useSource()
  const list = useAsync((signal) => api.ontoList(signal), [])
  const ontologies = useMemo(() => list.data?.ontologies ?? [], [list.data])
  const [oid, setOid] = useState<string>('')

  useEffect(() => {
    if (!oid && ontologies.length) {
      setOid([...ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))[0].id)
    }
  }, [oid, ontologies])

  const on = health?.layers
  const layers = ALL.filter((l) => !on || on.includes(l))

  return (
    <div className="page">
      <PageHeader eyebrow="Use anywhere" title="Use Strata your way"
        description="All four layers here, your own ontology under our layers, or any one layer in your own system, on your own data." />

      <section className="use-ways" aria-label="Three ways">
        <div className="use-way">
          <span className="use-way__tag">A</span>
          <h3>All four layers, here</h3>
          <p>Connect your data and use Ontology, Knowledge graph, Semantic and Context in this app, and agents over MCP.</p>
          <Link to="/tools/ontology/new">Start with your data <ArrowRight size={13} aria-hidden="true" /></Link>
        </div>
        <div className="use-way">
          <span className="use-way__tag">B</span>
          <h3>Your ontology, our layers</h3>
          <p>Already have an ontology (Strata Model, Ossie, dbt, a data dictionary)? It is used exactly, checked against your data, and the other layers run on top of it.</p>
          <Link to="/tools/ontology/new?mode=model">Use my ontology <ArrowRight size={13} aria-hidden="true" /></Link>
        </div>
        <div className="use-way">
          <span className="use-way__tag">C</span>
          <h3>One layer, in your system</h3>
          <p>Take only the layer you need: download it in an open format, run a ready-made copy with only that layer, or call it from your tools.</p>
          <a href="#layers">Pick a layer below <ArrowRight size={13} aria-hidden="true" /></a>
        </div>
      </section>

      <section className="use-ways" aria-label="Ready-made copies">
        <div className="use-way">
          <PackageOpen size={18} aria-hidden="true" />
          <h3>A ready-to-run copy for another team</h3>
          <p>One zip with only the layers they need. They unzip it and double-click <code>start.bat</code>. Python only, no Docker; their data never moves.</p>
          <div className="use-way__links">
            <DownloadLink href="/api/bundle?layers=semantic" fallback="strata-semantic.zip"><Download size={13} aria-hidden="true" /> Semantic only</DownloadLink>
            <DownloadLink href="/api/bundle?layers=context" fallback="strata-context.zip"><Download size={13} aria-hidden="true" /> Context only</DownloadLink>
            <DownloadLink href="/api/bundle?layers=graph" fallback="strata-graph.zip"><Download size={13} aria-hidden="true" /> Knowledge graph only</DownloadLink>
            <DownloadLink href="/api/bundle" fallback="strata-all.zip"><Download size={13} aria-hidden="true" /> All layers</DownloadLink>
          </div>
        </div>
      </section>

      <h2 id="layers" className="sem-h">Each layer, in your own system</h2>
      {list.initialLoading && !list.data ? <LoadingState label="Loading" /> : null}
      {list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : null}
      {list.data && !ontologies.length ? (
        <EmptyState icon={PackageOpen} title="Build or import an ontology first"
          description="Each layer is made from an ontology: yours, or one Strata builds from your data."
          action={<Link to="/tools/ontology/new"><Button variant="primary" icon={<Plus size={15} />}>New ontology</Button></Link>} />
      ) : null}
      {oid ? (
        <>
          {ontologies.length > 1 ? (
            <div className="use-pick">
              <label htmlFor="use-onto">For the ontology</label>
              <select id="use-onto" className="input" value={oid} onChange={(e) => setOid(e.target.value)}>
                {ontologies.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
          ) : null}
          <div className="use-layers">
            {layers.map((l, i) => <UseElsewhere key={`${l}-${oid}`} layer={l} oid={oid} open={i === 0} />)}
          </div>
        </>
      ) : null}
    </div>
  )
}
