import { useEffect, useMemo, useState } from 'react'
import { Quote } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { OntoView } from '../../api/types'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { OntologyTerms } from './OntologyView'

/** Terms, filled from the ontology: each business thing is a card. */
export function TermsPage() {
  useDocumentTitle('Terms')
  const [rows, setRows] = useState<Array<{ id: string; name: string; created_at: string }>>([])
  const [oid, setOid] = useState<string | null>(null)
  const [view, setView] = useState<OntoView | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let stop = false
    api.ontoList().then((list) => {
      if (stop) return
      const ontologies = [...list.ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))
      setRows(ontologies)
      setOid((current) => current && ontologies.some((row) => row.id === current) ? current : ontologies[0]?.id ?? null)
      setLoading(false)
    }).catch((caught) => {
      if (!stop) { setError(caught); setLoading(false) }
    })
    return () => { stop = true }
  }, [])

  useEffect(() => {
    if (!oid) return
    let stop = false
    setView(null)
    api.ontoView(oid).then((next) => { if (!stop) setView(next) }).catch((caught) => { if (!stop) setError(caught) })
    return () => { stop = true }
  }, [oid])

  const choices = useMemo(() => rows, [rows])

  return (
    <div className="page page--fill terms-page">
      <header className="terms-page__head">
        <Quote size={20} aria-hidden="true" />
        <h1>Terms</h1>
        {choices.length > 1 ? (
          <select className="input" aria-label="Ontology" value={oid ?? ''} onChange={(e) => setOid(e.target.value)}>
            {choices.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        ) : null}
      </header>
      {loading ? <LoadingState label="Loading terms" /> : null}
      {error && !view ? <ErrorState error={error} onRetry={() => window.location.reload()} /> : null}
      {!loading && !error && !oid ? <p className="muted">No terms yet. Connect data and build an ontology first.</p> : null}
      {view ? <OntologyTerms view={view} onChange={(next) => { if (next) setView(next) }} /> : null}
      {error && view ? <p className="muted">{describeError(error).message}</p> : null}
    </div>
  )
}
