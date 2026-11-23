import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { KgEntity, KgGlobe, KgRef } from '../../api/types'
import { LoadingState } from '../../components/LoadingState'
import { ThingIcon } from '../../components/ThingIcon'
import { useAsync } from '../../hooks/useAsync'
import { EntityPicker } from './EntityPicker'
import { RecordCard } from './RecordCard'

/**
 * The record-first view of the knowledge graph (plan step 2.1): search for a
 * record, or start from one of a few real examples picked from the data, and
 * read it as a card. The dot picture stays below, for when someone wants it.
 */
export function RecordExplorer({ oid }: { oid: string }) {
  const globe = useAsync<KgGlobe>((signal) => api.kgGlobe(oid, signal), [oid])
  const [ref, setRef] = useState<KgRef | null>(null)

  // One real example per kind of thing, straight from the data.
  const picks = useMemo(() => {
    const seen = new Set<string>()
    const out: KgGlobe['nodes'] = []
    for (const n of globe.data?.nodes ?? []) {
      if (seen.has(n.thing)) continue
      seen.add(n.thing)
      out.push(n)
      if (out.length >= 6) break
    }
    return out
  }, [globe.data])

  useEffect(() => {
    if (!ref && picks.length) setRef({ set: picks[0].set, key: picks[0].key })
  }, [ref, picks])

  return (
    <section className="kgp" aria-label="Records">
      <div className="kgp__search">
        <EntityPicker oid={oid} label="Find a record" placeholder="Search by id or name, e.g. a customer or an order"
          onPick={(h) => setRef({ set: h.set, key: h.key })} />
      </div>

      {picks.length ? (
        <div className="startpicks" aria-label="Start from an example">
          <span className="kg-muted" style={{ fontSize: '0.82rem' }}>Start from:</span>
          {picks.map((p) => (
            <button key={`${p.set}|${p.key}`} type="button" className="startpick"
              onClick={() => setRef({ set: p.set, key: p.key })}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <ThingIcon size={14} /> <b>{p.label ?? p.key}</b>
              </span>
              <small>{p.thing}</small>
            </button>
          ))}
        </div>
      ) : null}

      {ref ? <Selected oid={oid} refr={ref} onOpen={setRef} /> : globe.loading
        ? <LoadingState label="Reading your records" /> : null}
    </section>
  )
}

function Selected({ oid, refr, onOpen }: { oid: string; refr: KgRef; onOpen: (r: KgRef) => void }) {
  const e = useAsync<KgEntity>((signal) => api.kgEntity(oid, refr.set, refr.key, signal), [oid, refr.set, refr.key])
  if (e.loading && !e.data) return <LoadingState label="Opening the record" />
  if (!e.data) return <p className="kg-muted">Could not open this record.</p>
  return <RecordCard entity={e.data} onOpen={onOpen} />
}
