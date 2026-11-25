import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Database } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { OntoField, OntoThing, OntoView } from '../../api/types'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ColumnPage, TablePage, placeOf } from './OntologyView'

/** Data catalog for the selected ontology: database, schema, table, column. */
export function DataPage() {
  useDocumentTitle('Data')
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [rows, setRows] = useState<Array<{ id: string; name: string; created_at: string }>>([])
  const [view, setView] = useState<OntoView | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const asked = params.get('oid')
  const pick = params.get('pick') ?? ''

  useEffect(() => {
    let stop = false
    api.ontoList().then((list) => {
      if (stop) return
      const ontologies = [...list.ontologies].sort((a, b) => b.created_at.localeCompare(a.created_at))
      setRows(ontologies)
      const oid = asked && ontologies.some((row) => row.id === asked) ? asked : ontologies[0]?.id
      if (oid && oid !== asked) setParams({ oid }, { replace: true })
      setLoading(false)
    }).catch((caught) => {
      if (!stop) { setError(caught); setLoading(false) }
    })
    return () => { stop = true }
  }, [asked, setParams])

  const oid = asked && rows.some((row) => row.id === asked) ? asked : rows[0]?.id ?? null

  useEffect(() => {
    if (!oid) return
    let stop = false
    setView(null)
    api.ontoView(oid).then((next) => { if (!stop) setView(next) }).catch((caught) => { if (!stop) setError(caught) })
    return () => { stop = true }
  }, [oid])

  const tree = useMemo(() => (view ? catalog(view) : []), [view])
  const choose = (next: string) => {
    if (next.startsWith('term:')) { navigate('/terms'); return }
    setParams({ oid: oid ?? '', pick: next })
  }

  return (
    <div className="page page--fill">
      <header className="terms-page__head">
        <Database size={20} aria-hidden="true" />
        <h1>Data</h1>
        {rows.length > 1 ? (
          <select className="input" aria-label="Ontology" value={oid ?? ''} onChange={(e) => setParams({ oid: e.target.value })}>
            {rows.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        ) : null}
      </header>
      {loading ? <LoadingState label="Loading data" /> : null}
      {error && !view ? <ErrorState error={error} onRetry={() => window.location.reload()} /> : null}
      {view ? (
        <div className="data-layout">
          <aside className="data-tree" aria-label="Tables">
            {tree.map((db) => (
              <div key={db.name}>
                <p>{db.name}</p>
                {db.schemas.map((schema) => (
                  <div key={schema.name}>
                    <p className="is-schema">{schema.name}</p>
                    {schema.tables.map((table) => (
                      <div key={table.raw}>
                        <button type="button" className={pick === `table:${table.raw}` ? 'is-on' : ''} onClick={() => choose(`table:${table.raw}`)}>{table.name}</button>
                        {table.fields.map((field) => (
                          <button key={field.key} type="button" className={`is-col ${pick === `col:${field.key}` ? 'is-on' : ''}`} onClick={() => choose(`col:${field.key}`)}>{field.column}</button>
                        ))}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </aside>
          <div className="data-main">
            {view && pick.startsWith('table:') ? (
              <TableMatch view={view} table={pick.slice(6)} onOpen={choose} />
            ) : null}
            {view && pick.startsWith('col:') ? <ColumnMatch view={view} fieldKey={pick.slice(4)} /> : null}
            {view && !pick ? <p className="muted">Choose a table or a column. This is the data for {view.name}.</p> : null}
          </div>
        </div>
      ) : null}
      {error && view ? <p className="muted">{describeError(error).message}</p> : null}
    </div>
  )
}

type TableNode = { raw: string; name: string; fields: OntoField[]; thing: OntoThing }

function catalog(view: OntoView) {
  const dbs = new Map<string, Map<string, TableNode[]>>()
  for (const thing of view.things) {
    for (const raw of thing.tables) {
      const place = placeOf(raw, view.sources[0] || view.name)
      const schemas = dbs.get(place.database) ?? new Map<string, TableNode[]>()
      const tables: TableNode[] = schemas.get(place.schema) ?? []
      if (!tables.some((item) => item.raw === raw)) {
        tables.push({
          raw, name: place.table, thing,
          fields: thing.fields.filter((field) => !field.table || field.table === raw || thing.tables.length === 1),
        })
      }
      schemas.set(place.schema, tables)
      dbs.set(place.database, schemas)
    }
  }
  return [...dbs.entries()].map(([name, schemas]) => ({
    name,
    schemas: [...schemas.entries()].map(([schema, tables]) => ({ name: schema, tables })),
  }))
}

function TableMatch({ view, table, onOpen }: { view: OntoView; table: string; onOpen: (id: string) => void }) {
  const thing = view.things.find((item) => item.tables.includes(table))
  if (!thing) return <p className="muted">This table is not in {view.name}.</p>
  return <TablePage view={view} thing={thing} table={table} onOpen={onOpen} />
}

function ColumnMatch({ view, fieldKey }: { view: OntoView; fieldKey: string }) {
  const thing = view.things.find((item) => item.fields.some((field) => field.key === fieldKey))
  const field = thing?.fields.find((item) => item.key === fieldKey)
  if (!thing || !field) return <p className="muted">This column is not in {view.name}.</p>
  return <ColumnPage view={view} thing={thing} field={field} attribute={false} />
}
