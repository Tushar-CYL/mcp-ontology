import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight, Check, ChevronLeft, CircleCheck, CircleDashed, Copy, Download, FileJson, GitBranch, KeyRound,
  Link2, Lock, MessageSquarePlus, Pencil, Plus, Search, Send, Share2, ShieldCheck, Table2, Trash2,
  TriangleAlert, Waypoints, X,
} from 'lucide-react'
import { api, describeError } from '../../api/client'
import { DownloadLink } from '../../components/DownloadLink'
import { UseElsewhere } from '../../components/UseElsewhere'
import { useSuggestions } from '../../hooks/useSuggestions'
import type { OntoAsk, OntoCheck, OntoField, OntoThing, OntoView as View } from '../../api/types'
import { Button } from '../../components/Button'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { readSession } from '../../session'
import { cx } from '../../utils/cx'
import {
  CHECK, SET_BY, conflictCount, filterFields,
  formatCount, matchLabel, relatedThings, thingProof,
} from '../../utils/onto'
import { OntoMap } from './OntoMap'
import { RulesPanel } from './RulesPanel'
import { WhatDepends } from '../../components/WhatDepends'
export type Tab = 'overview' | 'map' | 'ask' | 'use'

const CHECK_ICON: Record<OntoCheck, typeof CircleCheck> = {
  verified: CircleCheck, conflict: TriangleAlert, unchecked: CircleDashed,
}

/** The ontology: overview (things and fields), map, and how to use it. */
export function OntologyView({ view, tab, onTab, onChange }: {
  view: View
  tab: Tab
  onTab: (tab: Tab) => void
  onChange: (next?: View) => void
  onDeleted: () => void
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [onlyConflicts, setOnlyConflicts] = useState(false)

  const locked = tab === 'overview' || tab === 'ask' || tab === 'map'
  return (
    <div className={cx('onto', locked ? 'onto--locked' : 'onto--scroll')}>
      <nav className="onto-tabs" role="tablist" aria-label="Views">
        {([['overview', 'Overview', Table2], ['map', 'Map', Share2],
          ['ask', 'Ask', MessageSquarePlus],
          ['use', 'Use it', ArrowRight]] as const)
          .map(([id, label, Icon]) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id}
              className={cx('onto-tab', tab === id && 'is-active')} onClick={() => onTab(id)}>
              <Icon size={15} aria-hidden="true" /> {label}
            </button>
          ))}
      </nav>

      {tab === 'overview' ? (
        <Explorer view={view} selected={selected} onSelect={setSelected}
          onlyConflicts={onlyConflicts} onOnlyConflicts={setOnlyConflicts} onChange={onChange} />
      ) : null}
      {tab === 'map' ? (
        <div className="onto-fill">
          <OntoMap view={view} selected={view.things.find((t) => t.key === selected)?.name}
            onOpen={(key) => { setSelected(key); onTab('overview') }} />
        </div>
      ) : null}
      {tab === 'ask' ? <div className="onto-fill"><AskPanel view={view} /></div> : null}
      {tab === 'use' ? (
        <div className="onto-scroll">
          <UseIt view={view} />
        </div>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ overview */
const OBJECT_FILTERS = ['Terms', 'Column Attributes', 'SQL Attributes', 'Links', 'Tables', 'Columns'] as const
type HitKind = typeof OBJECT_FILTERS[number]
type Hit = { id: string; kind: HitKind; title: string; body: string; path: string; thing: string }

function Explorer({ view, selected, onSelect, onlyConflicts, onOnlyConflicts, onChange }: {
  view: View
  selected: string | null
  onSelect: (key: string | null) => void
  onlyConflicts: boolean
  onOnlyConflicts: (on: boolean) => void
  onChange: (next?: View) => void
}) {
  const picked = selected && !selected.includes(':') ? `term:${selected}` : selected
  return (
    <>
      <div className="onto-fill" hidden={picked != null}>
        <ThingList view={view} onOpen={(hit) => onSelect(hit.id)} />
      </div>
      {picked ? (
        <div className="onto-page onto-page--scroll">
          <button type="button" className="term__back" onClick={() => onSelect(null)}>
            <ChevronLeft size={15} aria-hidden="true" /> Back
          </button>
          <Opened view={view} picked={picked} onlyConflicts={onlyConflicts}
            onOnlyConflicts={onOnlyConflicts} onChange={onChange}
            onOpen={(id) => onSelect(id)} />
        </div>
      ) : null}
    </>
  )
}

function ThingList({ view, onOpen }: {
  view: View
  onOpen: (hit: Hit) => void
}) {
  const navigate = useNavigate()
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const [inDescription, setInDescription] = useState(true)
  const [openMenu, setOpenMenu] = useState<string | null>(null)
  const [objects, setObjects] = useState<Set<string>>(() => new Set(OBJECT_FILTERS))
  const [chip, setChip] = useState<'All' | HitKind>('All')
  const roles = [...new Set(view.things.flatMap((thing) => thing.fields.map((field) => field.role_label).filter(Boolean)))]
  const tagOptions = ['Blanks', ...roles]
  const [tags, setTags] = useState<Set<string>>(() => new Set(tagOptions))
  const dataOptions = [...new Set(view.sources.length ? view.sources : [view.name])]
  const [dataOn, setDataOn] = useState<Set<string>>(() => new Set(dataOptions))
  useEffect(() => {
    setTags(new Set(['Blanks', ...roles]))
    setDataOn(new Set(view.sources.length ? view.sources : [view.name]))
  }, [view.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const needle = query.trim().toLowerCase()
  const searching = needle.length > 0
  const termsOnly = objects.size === 1 && objects.has('Terms')
  const showAllTerms = termsOnly || chip === 'Terms'
  const allowsData = (thing: OntoThing) => {
    if (!dataOn.size) return false
    if (dataOn.size >= dataOptions.length) return true
    return [...dataOn].some((source) => thing.tables.some((table) => table.includes(source)) || source === view.name)
  }
  const allowsTags = (thing: OntoThing) => {
    if (!tags.size) return false
    if (tags.size >= tagOptions.length) return true
    const thingTags = [...new Set(thing.fields.map((field) => field.role_label).filter(Boolean))]
    return (tags.has('Blanks') && thingTags.length === 0) || thingTags.some((tag) => tags.has(tag))
  }
  const textHit = (title: string, body: string) => {
    if (!needle) return true
    if (title.toLowerCase().includes(needle)) return true
    return inDescription && body.toLowerCase().includes(needle)
  }
  const termPool = view.things.filter((thing) => allowsData(thing) && allowsTags(thing))
  // Terms = every business card (9). Selecting Terms must not shrink that list.
  const showCards = !searching || showAllTerms
  const things = termPool.filter((thing) => {
    if (showAllTerms) return true
    if (!objects.has('Terms') && !searching) {
      return (objects.has('Column Attributes') && thing.fields.length)
        || (objects.has('Tables') && thing.tables.length)
        || (objects.has('Links') && view.links.some((link) => link.from_thing === thing.name || link.to_thing === thing.name))
        || (objects.has('SQL Attributes') && view.calculations.some((calc) => calc.thing === thing.name))
        || (objects.has('Columns') && thing.fields.length)
    }
    if (!searching) return objects.has('Terms') || objects.size === OBJECT_FILTERS.length
    return textHit(thing.name, thing.description)
  })
  const allHits = (() => {
    if (!searching || !dataOn.size || !tags.size || !objects.size) return [] as Hit[]
    const out: Hit[] = []
    const seen = new Set<string>()
    for (const thing of view.things) {
      if (!allowsData(thing) || !allowsTags(thing)) continue
      const add = (hit: Hit) => {
        if (seen.has(hit.id) || !textHit(hit.title, hit.body) || !objects.has(hit.kind)) return
        seen.add(hit.id)
        out.push(hit)
      }
      if (objects.has('Terms')) add({ id: `term:${thing.key}`, kind: 'Terms', title: thing.name, body: thing.description, path: '', thing: thing.key })
      if (objects.has('Tables')) for (const table of thing.tables) add({ id: `table:${table}`, kind: 'Tables', title: table.split('.').pop() || table, body: '', path: table, thing: thing.key })
      if (objects.has('Column Attributes')) for (const field of thing.fields) add({ id: `attr:${field.key}`, kind: 'Column Attributes', title: field.label || field.column, body: field.meaning, path: `Term: ${thing.name}`, thing: thing.key })
      if (objects.has('Columns')) for (const field of thing.fields) add({ id: `col:${field.key}`, kind: 'Columns', title: field.column, body: field.meaning, path: field.table || thing.tables[0] || '', thing: thing.key })
      if (objects.has('Links')) for (const link of view.links) if (link.from_thing === thing.name) add({ id: `link:${link.key}`, kind: 'Links', title: link.label, body: `${link.from} = ${link.to}`, path: link.to_thing, thing: thing.key })
      if (objects.has('SQL Attributes')) for (const calc of view.calculations) if (calc.thing === thing.name) add({ id: `sql:${thing.key}:${calc.name}`, kind: 'SQL Attributes', title: calc.name, body: calc.description, path: thing.name, thing: thing.key })
    }
    return out
  })()
  const shownHits = chip === 'All' ? allHits : allHits.filter((hit) => hit.kind === chip)
  const counts = OBJECT_FILTERS
    .map((kind) => {
      const count = kind === 'Terms'
        ? termPool.length
        : allHits.filter((hit) => hit.kind === kind).length
      return [kind, count] as const
    })
    .filter((row) => objects.has(row[0]) && row[1] > 0)
  const linkCount = (name: string) => view.links.filter((l) => l.from_thing === name || l.to_thing === name).length
  const relatedCount = (name: string) => {
    const r = relatedThings(view.links, name)
    return r.direct.length + r.indirect.length
  }
  const resetAll = () => {
    setDraft('')
    setQuery('')
    setChip('All')
    setObjects(new Set(OBJECT_FILTERS))
    setTags(new Set(tagOptions))
    setDataOn(new Set(dataOptions))
    setInDescription(true)
  }

  return (
    <div className="onto-page onto-page--fixed">
      <div className="onto-page__chrome">
        <div className="term-filters" aria-label="Filters">
          <span className="term-filters__label">Filters</span>
          <FilterMenu id="objects" open={openMenu} setOpen={setOpenMenu} label="Objects" options={[...OBJECT_FILTERS]} selected={objects} onChange={(next) => {
            setObjects(next)
            setChip('All')
            if (next.size === 1 && next.has('Terms')) { setDraft(''); setQuery('') }
          }} />
          <FilterMenu id="tags" open={openMenu} setOpen={setOpenMenu} label="Tags" options={tagOptions} selected={tags} onChange={setTags} searchable />
          <FilterMenu id="data" open={openMenu} setOpen={setOpenMenu} label="Data" options={dataOptions} selected={dataOn} onChange={setDataOn} />
          <label className="term-filters__desc"><input type="checkbox" checked={inDescription} onChange={(e) => setInDescription(e.target.checked)} /> Search in description</label>
        </div>
        <form className="tlist-search" onSubmit={(event) => { event.preventDefault(); setQuery(draft.trim()); setChip('All') }}>
          <Search size={16} aria-hidden="true" />
          <input value={draft} placeholder="Search Terms..." aria-label="Search terms"
            onChange={(e) => { setDraft(e.target.value); if (!e.target.value.trim()) { setQuery(''); setChip('All') } }} />
          {draft ? <button type="button" aria-label="Clear search" onClick={() => { setDraft(''); setQuery(''); setChip('All') }}><X size={15} /></button> : null}
          <Button type="submit" size="sm" variant="primary">Apply</Button>
          <Button type="button" size="sm" variant="ghost" onClick={resetAll}>Reset</Button>
        </form>
        {searching ? (
          <div className="hit-chips">
            <button type="button" className={chip === 'All' ? 'is-on' : ''} onClick={() => setChip('All')}>All {allHits.length}</button>
            {counts.map(([kind, count]) => (
              <button key={kind} type="button" className={chip === kind ? 'is-on' : ''} onClick={() => {
                setChip(kind)
                if (kind === 'Terms') { setDraft(''); setQuery('') }
              }}>{kind} {count}</button>
            ))}
          </div>
        ) : (
          <p className="tlist-count">{things.length} of {view.things.length} terms</p>
        )}
      </div>
      <div className="onto-page__scroll">
        {showCards ? (
          <div className="tlist">
            {things.map((t) => {
              const { proved, disagrees, todo } = thingProof(t)
              const sql = view.calculations.filter((c) => c.thing === t.name).length
              const status = disagrees ? { label: `${disagrees} need a look`, cls: 'is-bad' }
                : todo ? { label: `${todo} to check`, cls: 'is-warn' }
                  : { label: 'Confirmed', cls: 'is-ok' }
              const cells: Array<[string, string]> = [
                ['Column Attributes', String(t.fields.length)],
                ['SQL Attributes', String(sql)],
                ['Related Terms', String(relatedCount(t.name))],
                ['Zones', view.name],
                ['Links', String(linkCount(t.name))],
                ['Records', t.records ? formatCount(t.records) : '–'],
                ['Proved', String(proved)],
              ]
              return (
                <button key={t.key} type="button" className="tlist-card" onClick={() => onOpen({ id: `term:${t.key}`, kind: 'Terms', title: t.name, body: t.description, path: '', thing: t.key })}>
                  <div className="tlist-card__head">
                    <div className="tlist-card__id"><h3>{t.name}</h3></div>
                    <span className={cx('term__status', status.cls)}>{status.label}</span>
                  </div>
                  <p className="tlist-card__desc">{t.description || 'No Description Available'}</p>
                  <div className="term-grid">
                    {cells.map(([label, value]) => (
                      <div key={label}><header>{label}</header><p><strong>{value}</strong></p></div>
                    ))}
                  </div>
                </button>
              )
            })}
            {!things.length ? <p className="onto-list__empty">Nothing matches these filters.</p> : null}
          </div>
        ) : null}
        {searching && !showCards ? (
          <div className="hit-list">
            {shownHits.map((hit) => (
              <button key={hit.id} type="button" className="hit-row" onClick={() => {
                if (hit.kind === 'Tables' || hit.kind === 'Columns') {
                  navigate(`/data?oid=${encodeURIComponent(view.id)}&pick=${encodeURIComponent(hit.id)}`)
                  return
                }
                onOpen(hit)
              }}>
                <span>
                  <strong><Mark text={hit.title} query={needle} /></strong>
                  {hit.body ? <em><Mark text={hit.body} query={needle} /></em> : null}
                  {hit.path ? <small>{hit.path}</small> : null}
                </span>
                <b>{hit.kind === 'Column Attributes' ? 'Column Attribute' : hit.kind === 'SQL Attributes' ? 'SQL Attribute' : hit.kind.replace(/s$/, '')}</b>
              </button>
            ))}
            {!shownHits.length ? (
              <div className="hit-empty">
                <Search size={28} aria-hidden="true" />
                <strong>No Results Match Your Search</strong>
                <span>Don't give up, search harder!</span>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function Mark({ text, query }: { text: string; query: string }) {
  const at = query ? text.toLowerCase().indexOf(query) : -1
  if (at < 0) return <>{text}</>
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + query.length)}</mark>{text.slice(at + query.length)}</>
}

/** The terms list and the page you get when a card is opened. */
export function OntologyTerms({ view, onChange }: { view: View; onChange: (next?: View) => void }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [onlyConflicts, setOnlyConflicts] = useState(false)
  return (
    <Explorer view={view} selected={selected} onSelect={setSelected}
      onlyConflicts={onlyConflicts} onOnlyConflicts={setOnlyConflicts} onChange={onChange} />
  )
}

export function placeOf(raw: string, fallbackDb: string) {
  const parts = raw.split('.').filter(Boolean)
  const table = parts.pop() || raw
  const schema = parts.length > 1 ? parts.pop() || 'public' : 'public'
  const database = parts.join('.') || fallbackDb
  return { database, schema, table }
}

function Opened({ view, picked, onlyConflicts, onOnlyConflicts, onChange, onOpen }: {
  view: View
  picked: string
  onlyConflicts: boolean
  onOnlyConflicts: (on: boolean) => void
  onChange: (next?: View) => void
  onOpen: (id: string) => void
}) {
  const cut = picked.indexOf(':')
  const head = picked.slice(0, cut)
  const rest = picked.slice(cut + 1)
  const thing = head === 'table'
    ? view.things.find((item) => item.tables.includes(rest))
    : head === 'attr' || head === 'col'
      ? view.things.find((item) => item.fields.some((field) => field.key === rest))
      : head === 'link'
        ? view.things.find((item) => item.name === view.links.find((link) => link.key === rest)?.from_thing)
        : head === 'sql'
          ? view.things.find((item) => item.key === rest.slice(0, rest.indexOf(':')))
          : view.things.find((item) => item.key === rest)
  if (!thing) return <p className="muted">This is no longer in the ontology.</p>
  if (head === 'table') return <TablePage view={view} thing={thing} table={rest} onOpen={onOpen} />
  if (head === 'col' || head === 'attr') {
    const field = thing.fields.find((item) => item.key === rest)
    if (!field) return <p className="muted">This column is no longer in the ontology.</p>
    return <ColumnPage view={view} thing={thing} field={field} attribute={head === 'attr'} />
  }
  if (head === 'link') {
    const link = view.links.find((item) => item.key === rest)
    if (!link) return <p className="muted">This link is no longer in the ontology.</p>
    return (
      <section className="catalog">
        <h2>{link.label}</h2>
        <p>{link.from} = {link.to}</p>
        <p>{link.match != null ? matchLabel(link.match) : ''} {link.triples != null ? `· ${formatCount(link.triples)} records` : ''}</p>
        <button type="button" className="tchip" onClick={() => onOpen(`term:${thing.key}`)}>{thing.name}</button>
      </section>
    )
  }
  if (head === 'sql') {
    const calc = view.calculations.find((item) => item.thing === thing.name && rest.endsWith(item.name))
    return (
      <section className="catalog">
        <h2>{calc?.name || 'SQL attribute'}</h2>
        <p>{calc?.description || 'No description.'}</p>
        {calc ? <pre className="catalog__sql">{calc.expression}</pre> : null}
      </section>
    )
  }
  return (
    <ThingDetail key={thing.key} view={view} thing={thing} query=""
      onlyConflicts={onlyConflicts} onOnlyConflicts={onOnlyConflicts} onChange={onChange}
      onOpen={(name) => { const next = view.things.find((item) => item.name === name); if (next) onOpen(`term:${next.key}`) }} />
  )
}

export function TablePage({ view, thing, table, onOpen }: { view: View; thing: OntoThing; table: string; onOpen: (id: string) => void }) {
  const place = placeOf(table, view.sources[0] || view.name)
  const columns = thing.fields.filter((field) => !field.table || field.table === table || thing.tables.length === 1)
  return (
    <section className="catalog" aria-label={place.table}>
      <h2>{place.table}</h2>
      <div className="tcard">
        <div className="tcard__head"><h3>Description</h3></div>
        <p className="term__desc">{thing.description || 'No description yet'}</p>
      </div>
      <div className="tcard">
        <div className="tcard__head"><h3>Information</h3></div>
        <div className="catalog__facts">
          <div><span>Type</span><strong>base table</strong></div>
          <div><span>Name</span><strong>{place.table}</strong></div>
          <div><span>Schema</span><strong>{place.schema}</strong></div>
          <div><span>Database</span><strong>{place.database}</strong></div>
          <div><span>Columns</span><strong>{columns.length}</strong></div>
          <div><span>Records</span><strong>{formatCount(thing.records)}</strong></div>
          <div><span>Term</span><button type="button" onClick={() => onOpen(`term:${thing.key}`)}>{thing.name}</button></div>
        </div>
      </div>
      <div className="tcard">
        <div className="tcard__head"><h3>Columns ({columns.length})</h3></div>
        <table className="catalog__table">
          <thead><tr><th>#</th><th>Name</th><th>Type</th><th>Certification</th></tr></thead>
          <tbody>
            {columns.map((field, index) => (
              <tr key={field.key}>
                <td>{index + 1}</td>
                <td><button type="button" onClick={() => onOpen(`col:${field.key}`)}>{field.column}</button></td>
                <td>{field.type || 'text'}</td>
                <td>{CHECK[field.check].label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function ColumnPage({ view, thing, field, attribute }: { view: View; thing: OntoThing; field: OntoField; attribute: boolean }) {
  const place = placeOf(field.table || thing.tables[0] || thing.name, view.sources[0] || view.name)
  const position = Math.max(1, thing.fields.findIndex((item) => item.key === field.key) + 1)
  return (
    <section className="catalog" aria-label={attribute ? field.label : field.column}>
      <h2>{attribute ? field.label : field.column}</h2>
      <div className="tcard">
        <div className="tcard__head"><h3>Description</h3></div>
        <p className="term__desc">{field.meaning || 'No description yet'}</p>
        {field.proof ? <p className="muted">{field.proof}</p> : null}
      </div>
      <div className="tcard">
        <div className="tcard__head"><h3>Information</h3></div>
        <div className="catalog__facts">
          <div><span>{attribute ? 'Attribute' : 'Column'}</span><strong>{attribute ? field.label : field.column}</strong></div>
          <div><span>Data type</span><strong>{field.type || 'text'}</strong></div>
          <div><span>Table</span><strong>{place.table}</strong></div>
          <div><span>Position</span><strong>{position}</strong></div>
          <div><span>Role</span><strong>{field.role_label || '—'}</strong></div>
          <div><span>Certification</span><strong>{CHECK[field.check].label}</strong></div>
          <div><span>Set by</span><strong>{SET_BY[field.by] ?? field.by}</strong></div>
          <div><span>Term</span><strong>{thing.name}</strong></div>
        </div>
      </div>
      {field.links_to ? <p>Links to {field.links_to}</p> : null}
      {field.personal ? <p>Personal data: {field.personal}</p> : null}
      <p className="muted">Database {place.database} · schema {place.schema}</p>
    </section>
  )
}

function ThingDetail({ view, thing, query, onlyConflicts, onOnlyConflicts, onChange, onOpen }: {
  view: View
  thing: OntoThing
  query: string
  onlyConflicts: boolean
  onOnlyConflicts: (on: boolean) => void
  onChange: (next?: View) => void
  onOpen: (thingName: string) => void
}) {
  const toast = useToast()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(thing.name)
  const [description, setDescription] = useState(thing.description)
  const [editing, setEditing] = useState<string | null>(null)
  const [sqlOpen, setSqlOpen] = useState(false)
  const [sqlName, setSqlName] = useState('')
  const [sqlText, setSqlText] = useState('')
  const [sqlNote, setSqlNote] = useState('')
  const [sqlDesc, setSqlDesc] = useState('')
  const [madeSql, setMadeSql] = useState<Array<{ name: string; description: string; expression: string }>>([])
  const fields = filterFields(thing.fields, query, onlyConflicts)
  const links = view.links.filter((l) => l.from_thing === thing.name || l.to_thing === thing.name)
  const calcs = [...view.calculations.filter((c) => c.thing === thing.name), ...madeSql]
  const bad = conflictCount(thing)
  const { direct: related, indirect: relatedVia } = relatedThings(view.links, thing.name)
  const { disagrees, todo } = thingProof(thing)
  const status = disagrees ? { label: `${disagrees} need a look`, cls: 'is-bad' }
    : todo ? { label: `${todo} to check`, cls: 'is-warn' }
      : { label: 'Confirmed by the data', cls: 'is-ok' }

  const saveThing = async () => {
    try {
      onChange(await api.ontoEditThing(view.id, { key: thing.key, name, description }))
      setRenaming(false)
    } catch (e) {
      toast.push({ title: 'Not saved', message: describeError(e).message, tone: 'error' })
    }
  }

  return (
    <section className="term" aria-label={thing.name}>
      <header className="term__head">
        <div className="term__id">
          <div className="term__title">
            {renaming
              ? <input className="input" value={name} aria-label="Name" onChange={(e) => setName(e.target.value)} />
              : <h2>{thing.name}</h2>}
            <span className={cx('term__status', status.cls)}>{status.label}</span>
          </div>
        </div>
        <div className="term__actions">
          {renaming ? (
            <>
              <Button size="sm" variant="ghost" onClick={() => { setRenaming(false); setName(thing.name); setDescription(thing.description) }}>Cancel</Button>
              <Button size="sm" variant="primary" icon={<Check size={14} />} onClick={saveThing}>Save</Button>
            </>
          ) : (
            <Button size="sm" variant="primary" icon={<Pencil size={14} />} onClick={() => setRenaming(true)}>Edit</Button>
          )}
          <Button size="sm" variant="primary" onClick={() => { setSqlOpen(true); setSqlNote('') }}>Create New SQL Attribute</Button>
        </div>
      </header>

      <div className="term__body">
        <div className="term__main">
          <div className="tcard">
            <div className="tcard__head"><h3>Description</h3></div>
            {renaming ? (
              <textarea className="input input--area" rows={3} value={description} aria-label="Description"
                onChange={(e) => setDescription(e.target.value)} />
            ) : (
              <p className="term__desc">{thing.description || <span className="muted">No description yet</span>}</p>
            )}
            <WhatDepends key={thing.name} oid={view.id} kind="thing" target={thing.name} compact />
          </div>

          <div className="tcard">
            <div className="tcard__head"><h3>Synonyms</h3></div>
            <p className="term__desc muted">None</p>
          </div>

          <div className="tcard">
            <div className="tcard__head"><h3>Entities <span className="tcard__count">{thing.tables.length}</span></h3></div>
            {thing.tables.length ? (
              <div className="tchips">{thing.tables.map((table) => <code key={table} className="tchip">{table}</code>)}</div>
            ) : <p className="term__desc muted">None</p>}
          </div>

          <div className="tcard">
            <div className="tcard__head"><h3>Zones</h3></div>
            <div className="tchips"><span className="tchip">{view.name}</span></div>
          </div>

          {related.length || relatedVia.length ? (
            <div className="tcard">
              <div className="tcard__head"><h3>Related things <span className="tcard__count">{related.length + relatedVia.length}</span></h3></div>
              {related.length ? (
                <div className="tchips">
                  {related.map((n) => (
                    <button key={n} type="button" className="tchip" onClick={() => onOpen(n)}>{n}</button>
                  ))}
                </div>
              ) : null}
              {relatedVia.length ? (
                <>
                  <p className="tcard__sub">Connected through a shared record</p>
                  <div className="tchips">
                    {relatedVia.map((r) => (
                      <button key={r.thing} type="button" className="tchip tchip--via" onClick={() => onOpen(r.thing)}>
                        {r.thing} <small>via {r.through}</small>
                      </button>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          ) : null}

          <div className="tcard">
            <div className="tcard__head">
              <h3>Column Attributes <span className="tcard__count">{thing.fields.length}</span></h3>
              {bad ? (
                <label className="term__filter">
                  <input type="checkbox" checked={onlyConflicts} onChange={(e) => onOnlyConflicts(e.target.checked)} />
                  Only fields to check ({bad})
                </label>
              ) : null}
            </div>
            <div className="onto-fields">
              <div className="onto-fields__head" aria-hidden="true">
                <span>Attribute Name</span><span>Description</span><span>Type</span><span>Certification</span><span />
              </div>
              {fields.map((f) => editing === f.key ? (
                <FieldEditor key={f.key} oid={view.id} field={f} roles={view.roles}
                  onDone={(next) => { setEditing(null); if (next) onChange(next) }} />
              ) : (
                <FieldRow key={f.key} field={f} onEdit={() => setEditing(f.key)} onOpen={onOpen} />
              ))}
              {!fields.length ? <p className="onto-fields__empty">No field matches.</p> : null}
            </div>
          </div>

          <div className="tcard">
            <div className="tcard__head"><h3>Links <span className="tcard__count">{links.length}</span></h3></div>
            <ul className="onto-links">
              {links.map((l) => {
                const other = l.from_thing === thing.name ? l.to_thing : l.from_thing
                return (
                  <li key={l.key}>
                    <Link2 size={16} aria-hidden="true" />
                    <div>
                      <button type="button" className="onto-links__title" onClick={() => onOpen(other)}>{l.label}</button>
                      <p>{l.triples != null
                        ? <span>{formatCount(l.triples)} times in the data{l.relation ? <> · <code>{l.relation}</code></> : null}</span>
                        : <><code>{l.from}</code> = <code>{l.to}</code></>}
                        {l.match != null ? <span className="onto-pill onto-pill--ok">{matchLabel(l.match)}</span> : null}
                        {l.declared ? <span className="onto-pill">from {l.declared}</span> : null}
                      </p>
                    </div>
                  </li>
                )
              })}
              {!links.length ? <li className="onto-fields__empty">{thing.name} is not linked to other things.</li> : null}
              {view.built?.hidden_relations ? (
                <li className="onto-links__more">
                  Plus {formatCount(view.built.hidden_relations)} rarer relations
                  ({formatCount(view.built.hidden_triples ?? 0)} triples) in the whole graph, counted but not listed.
                </li>
              ) : null}
            </ul>
          </div>

          <div className="tcard">
            <div className="tcard__head"><h3>SQL Attributes <span className="tcard__count">{calcs.length}</span></h3></div>
            {calcs.length ? (
              <div className="onto-calcs">
                {calcs.map((c) => (
                  <div key={c.name}><strong>{c.name}</strong><code>{c.expression}</code>{c.description ? <p>{c.description}</p> : null}</div>
                ))}
              </div>
            ) : <p className="term__desc muted">SQL Attribute Does Not Exist</p>}
          </div>
        </div>
      </div>
      {sqlOpen ? (
        <div className="sql-modal" role="presentation" onMouseDown={() => setSqlOpen(false)}>
          <form className="sql-modal__card" role="dialog" aria-label="Create New SQL Attribute" onMouseDown={(event) => event.stopPropagation()}
            onSubmit={(event) => {
              event.preventDefault()
              if (!sqlName.trim() || !sqlText.trim()) return
              setMadeSql((rows) => [...rows, { name: sqlName.trim(), description: sqlDesc.trim(), expression: sqlText.trim() }])
              setSqlName(''); setSqlDesc(''); setSqlText(''); setSqlOpen(false)
            }}>
            <header><h2>Create New SQL Attribute</h2><button type="button" aria-label="Close" onClick={() => setSqlOpen(false)}>×</button></header>
            <label>Attribute Name<input className="input" value={sqlName} onChange={(e) => setSqlName(e.target.value)} /></label>
            <label>Description (Optional)<textarea className="input input--area" rows={2} value={sqlDesc} onChange={(e) => setSqlDesc(e.target.value)} /></label>
            <label>SQL<textarea className="input input--area sql-modal__sql" rows={6} placeholder="SELECT ..." value={sqlText} onChange={(e) => setSqlText(e.target.value)} /></label>
            {sqlNote ? <p className="muted">{sqlNote}</p> : null}
            <div className="onto-row">
              <Button type="button" size="sm" variant="ghost" onClick={() => setSqlNote(/^(select|with)\b/i.test(sqlText.trim()) ? 'Looks like a query.' : 'Start with SELECT or WITH.')}>Validate SQL</Button>
              <Button type="submit" size="sm" variant="primary" disabled={!sqlName.trim() || !sqlText.trim()}>Create</Button>
            </div>
          </form>
        </div>
      ) : null}
    </section>
  )
}

function FilterMenu({ id, open, setOpen, label, options, selected, onChange, searchable = false }: {
  id: string
  open: string | null
  setOpen: (id: string | null) => void
  label: string
  options: string[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
  searchable?: boolean
}) {
  const box = useRef<HTMLDivElement>(null)
  const [q, setQ] = useState('')
  const showing = open === id
  const all = options.length > 0 && options.every((option) => selected.has(option))
  const shown = options.filter((option) => option.toLowerCase().includes(q.trim().toLowerCase()))
  const toggle = (option: string) => {
    const next = new Set(selected)
    if (next.has(option)) next.delete(option)
    else next.add(option)
    onChange(next)
  }
  useEffect(() => {
    if (!showing) return
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(null)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [showing, setOpen])
  const summary = all ? 'All' : selected.size ? `Selected (${selected.size})` : 'None'
  return (
    <div className={cx('filter-menu', !all && 'is-narrow')} ref={box}>
      <span>{label}</span>
      <button type="button" aria-expanded={showing} onClick={() => setOpen(showing ? null : id)}>
        {summary}
      </button>
      {showing ? (
        <div className="filter-menu__pop">
          <header>
            <span>Filter by</span>
            <button type="button" onClick={() => onChange(all ? new Set() : new Set(options))}>{all ? 'Deselect all' : 'Select all'}</button>
          </header>
          {searchable ? <input className="input" placeholder={`Search ${label.toLowerCase()}`} value={q} onChange={(e) => setQ(e.target.value)} /> : null}
          {shown.map((option) => (
            <label key={option}>
              <input type="checkbox" checked={selected.has(option)} onChange={() => toggle(option)} />
              {option}
            </label>
          ))}
          {!shown.length ? <p>No tags exist yet</p> : null}
        </div>
      ) : null}
    </div>
  )
}

function FieldRow({ field, onEdit, onOpen }: { field: OntoField; onEdit: () => void; onOpen: (thing: string) => void }) {
  const check = CHECK[field.check]
  const Icon = CHECK_ICON[field.check]
  return (
    <div className={cx('onto-field', `is-${field.check}`)}>
      <div className="onto-field__name">
        <span>{field.role === 'identifier' ? <KeyRound size={13} aria-label="Key" /> : null} {field.label}</span>
        <code>{field.column}</code>
      </div>
      <div className="onto-field__meaning">
        {field.meaning}
        {field.links_to ? (
          <button type="button" className="onto-field__link" onClick={() => onOpen(field.links_to!)}>
            <ArrowRight size={12} aria-hidden="true" /> {field.links_to}
          </button>
        ) : null}
        {field.personal ? (
          <span className="onto-field__personal" title="Personal data: Ask and agents avoid showing these values unless a question is about one record">
            <Lock size={12} aria-hidden="true" /> Personal data ({field.personal})
          </span>
        ) : null}
      </div>
      <div className="onto-field__type">
        <span className="onto-pill">{field.role_label}</span>
        {field.unit ? <span className="onto-pill onto-pill--unit">{field.unit}</span> : null}
      </div>
      <div className="onto-field__check" title={check.hint}>
        <span className={`onto-check onto-check--${field.check}`}><Icon size={14} aria-hidden="true" /> {check.label}</span>
        {field.proof ? <span className="onto-field__proof">{field.proof}</span> : null}
        <span className="onto-field__by">Set by {SET_BY[field.by]}</span>
        {field.review === 'approved' ? <span className="onto-field__review is-approved">Approved by a person</span> : null}
        {field.review === 'rejected' ? <span className="onto-field__review is-rejected">Rejected by a person: not used in answers</span> : null}
        {field.review === 'needs_you' ? <span className="onto-field__review is-open">Waiting for a person</span> : null}
      </div>
      <div className="onto-field__edit">
        <button type="button" onClick={onEdit} aria-label={`Edit ${field.label}`}><Pencil size={14} /></button>
      </div>
    </div>
  )
}

function FieldEditor({ oid, field, roles, onDone }: {
  oid: string
  field: OntoField
  roles: Record<string, string>
  onDone: (next?: View) => void
}) {
  const toast = useToast()
  const [label, setLabel] = useState(field.label)
  const [meaning, setMeaning] = useState(field.meaning)
  const [role, setRole] = useState(field.role)
  const [unit, setUnit] = useState(field.unit ?? '')
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try {
      onDone(await api.ontoEditField(oid, { key: field.key, label, meaning, role, unit }))
      toast.push({ title: `Saved ${label}`, tone: 'success' })
    } catch (e) {
      toast.push({ title: 'Not saved', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="onto-field onto-field--editing">
      <div className="onto-field__name">
        <input className="input" value={label} aria-label="Field name" onChange={(e) => setLabel(e.target.value)} />
        <code>{field.column}</code>
      </div>
      <div className="onto-field__meaning">
        <textarea className="input input--area" rows={3} value={meaning} aria-label="Meaning"
          onChange={(e) => setMeaning(e.target.value)} />
      </div>
      <div className="onto-field__type">
        <select className="input" value={role} aria-label="Type" onChange={(e) => setRole(e.target.value)}>
          {Object.entries(roles).map(([id, text]) => <option key={id} value={id}>{text}</option>)}
        </select>
        <input className="input" value={unit} placeholder="Unit (EUR, kg…)" aria-label="Unit"
          onChange={(e) => setUnit(e.target.value)} />
      </div>
      <div className="onto-field__save">
        <Button size="sm" variant="primary" icon={<Check size={14} />} loading={busy} onClick={save}>Save</Button>
        <Button size="sm" variant="ghost" onClick={() => onDone()}>Cancel</Button>
      </div>
      <div className="onto-field__impact">
        <WhatDepends oid={oid} kind="field" target={field.key} open />
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------- ask */
/* Ontology-only Ask: terms, tables, links, business rules (+ catalogue SQL). */

type Cell = string | number | boolean | null
type AskRecord = { set: string; key: string; thing: string; label: string }
type AskFact = { text: string; source: string; citation: string }
type AskMetric = { name: string; title: string; owner?: string | null }
type AskMsg = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sql?: string
  columns?: string[]
  rows?: Cell[][]
  truncated?: boolean
  stamp: number
  kind?: 'answer' | 'results' | 'cards' | 'error'
  records?: AskRecord[]
  metric?: AskMetric | null
  facts?: AskFact[]
  layers?: Array<{ layer: string; what: string }>
}

function fmtCell(v: Cell): string {
  if (v === null) return ''
  if (typeof v === 'number') {
    return Number.isInteger(v) ? formatCount(v) : v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  return String(v)
}

function clock(ms: number) {
  return new Date(ms).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })
}

function askProse(r: OntoAsk): string {
  const base = (r.explanation || '').trim()
  if (base) return /[.!?]$/.test(base) || base.includes('\n') ? base : `${base}.`
  if (r.metric?.title) return `${r.metric.title} answers this from the certified semantic layer.`
  if (r.answerable && r.things.length) {
    return `This answer uses ${r.things.join(', ')} from the published ontology.`
  }
  return (r.note || '').trim() || 'Not enough proven facts in this ontology to answer that yet.'
}

type AskConv = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: AskMsg[]
}

type AskStore = {
  activeId: string | null
  conversations: AskConv[]
}

function userKey() {
  return (readSession()?.email || 'anonymous').trim().toLowerCase()
}

function storeKey(oid: string) {
  return `onto-ask-store:${userKey()}:${oid}`
}

function emptyStore(): AskStore {
  return { activeId: null, conversations: [] }
}

function loadStore(oid: string): AskStore {
  try {
    const raw = localStorage.getItem(storeKey(oid))
    if (raw) {
      const parsed = JSON.parse(raw) as AskStore
      if (parsed && Array.isArray(parsed.conversations)) {
        return {
          activeId: parsed.activeId ?? parsed.conversations[0]?.id ?? null,
          conversations: parsed.conversations.slice(0, 40),
        }
      }
    }
    // Migrate older single-thread key (not user-scoped) into this user's first chat once.
    const legacy = localStorage.getItem(`onto-ask-chat:${oid}`)
    if (legacy) {
      const msgs = JSON.parse(legacy) as AskMsg[]
      if (Array.isArray(msgs) && msgs.length) {
        const id = `c-${Date.now()}`
        const title = msgs.find((m) => m.role === 'user')?.content.slice(0, 48) || 'Previous chat'
        const migrated: AskStore = {
          activeId: id,
          conversations: [{ id, title, createdAt: msgs[0]?.stamp || Date.now(), updatedAt: Date.now(), messages: msgs.slice(-200) }],
        }
        localStorage.setItem(storeKey(oid), JSON.stringify(migrated))
        return migrated
      }
    }
  } catch { /* ignore */ }
  return emptyStore()
}

function saveStore(oid: string, store: AskStore) {
  try {
    localStorage.setItem(storeKey(oid), JSON.stringify({
      activeId: store.activeId,
      conversations: store.conversations.slice(0, 40).map((c) => ({
        ...c, messages: c.messages.slice(-200),
      })),
    }))
  } catch { /* quota */ }
}

function titleFrom(msgs: AskMsg[]) {
  const q = msgs.find((m) => m.role === 'user')?.content.trim() || 'New chat'
  return q.length > 42 ? `${q.slice(0, 42)}…` : q
}

function downloadCsv(columns: string[], rows: Cell[][], name: string) {
  const esc = (v: Cell) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const body = [columns.join(','), ...rows.map((row) => row.map(esc).join(','))].join('\n')
  const blob = new Blob([body], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function AskPanel({ view }: { view: View }) {
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [panel, setPanel] = useState<'chat' | 'rules'>('chat')
  const [store, setStore] = useState<AskStore>(() => loadStore(view.id))
  const end = useRef<HTMLDivElement>(null)
  const skipScroll = useRef(true)
  const sugg = useSuggestions(view.id, 'ask', view.version)
  const active = store.conversations.find((c) => c.id === store.activeId) ?? null
  const msgs = active?.messages ?? []

  useEffect(() => {
    setStore(loadStore(view.id))
    setPanel('chat')
    skipScroll.current = true
  }, [view.id])

  useEffect(() => { saveStore(view.id, store) }, [view.id, store])

  useEffect(() => {
    if (skipScroll.current) { skipScroll.current = false; return }
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [msgs, busy, panel])

  const patchActive = (updater: (msgs: AskMsg[]) => AskMsg[]) => {
    setStore((prev) => {
      let conversations = [...prev.conversations]
      let activeId = prev.activeId
      if (!activeId || !conversations.some((c) => c.id === activeId)) {
        const id = `c-${Date.now()}`
        conversations = [{ id, title: 'New chat', createdAt: Date.now(), updatedAt: Date.now(), messages: [] }, ...conversations]
        activeId = id
      }
      conversations = conversations.map((c) => {
        if (c.id !== activeId) return c
        const messages = updater(c.messages)
        return { ...c, messages, title: titleFrom(messages), updatedAt: Date.now() }
      })
      return { activeId, conversations }
    })
  }

  const newChat = () => {
    const id = `c-${Date.now()}`
    setPanel('chat')
    setStore((prev) => ({
      activeId: id,
      conversations: [{ id, title: 'New chat', createdAt: Date.now(), updatedAt: Date.now(), messages: [] }, ...prev.conversations],
    }))
    skipScroll.current = true
  }

  const openChat = (id: string) => {
    setPanel('chat')
    setStore((prev) => ({ ...prev, activeId: id }))
    skipScroll.current = true
  }

  const removeChat = (id: string) => {
    setStore((prev) => {
      const conversations = prev.conversations.filter((c) => c.id !== id)
      const activeId = prev.activeId === id ? (conversations[0]?.id ?? null) : prev.activeId
      return { activeId, conversations }
    })
  }

  const send = async (raw: string) => {
    const q = raw.trim()
    if (!q || busy) return
    const now = Date.now()
    setDraft('')
    setBusy(true)
    setPanel('chat')
    patchActive((prev) => [...prev, { id: `u-${now}`, role: 'user', content: q, stamp: now }])
    try {
      const r = await api.ontoAsk(view.id, q)
      const prose = askProse(r)
      const stamp = Date.now()
      const mode = r.mode ?? (r.sql || r.columns.length ? 'query' : 'explain')
      const showSql = mode === 'query' && Boolean(r.sql)
      const showTable = mode === 'query' && r.answerable && r.columns.length > 0
      const next: AskMsg[] = [{
        id: `a-${stamp}`, role: 'assistant', kind: 'answer', stamp,
        content: prose, sql: showSql ? (r.sql || undefined) : undefined,
      }]
      if (showTable) {
        next.push({
          id: `r-${stamp}`, role: 'assistant', kind: 'results', stamp: stamp + 1,
          content: '', columns: r.columns, rows: r.rows, truncated: r.truncated,
        })
      } else if (!r.answerable && r.note && !prose.includes(r.note)) {
        next[0] = { ...next[0], content: `${prose}\n\n${r.note}` }
      }
      patchActive((prev) => [...prev, ...next])
    } catch (e) {
      patchActive((prev) => [...prev, {
        id: `e-${Date.now()}`, role: 'assistant', kind: 'error', stamp: Date.now(),
        content: describeError(e).message,
      }])
    } finally {
      setBusy(false)
    }
  }

  const starters = [
    ...sugg.items.slice(0, 2).map((item) => item.text),
    'What business rules do we have?',
    'Tell me about Customer Order',
    'How many customers are there?',
  ].filter((t, i, all) => all.indexOf(t) === i).slice(0, 6)

  const chats = [...store.conversations].sort((a, b) => b.updatedAt - a.updatedAt)
  const who = readSession()?.email || 'this browser'

  return (
    <div className="onto-chat onto-chat--split">
      <aside className="onto-chat__side" aria-label="Chats">
        <button type="button" className="onto-chat__new" onClick={newChat}>
          <Plus size={14} aria-hidden="true" /> New chat
        </button>
        <p className="onto-chat__side-label">Saved for {who}</p>
        <ul className="onto-chat__convos">
          {chats.map((c) => (
            <li key={c.id}>
              <button type="button" className={cx('onto-chat__convo', c.id === store.activeId && panel === 'chat' && 'is-on')}
                onClick={() => openChat(c.id)} title={c.title}>
                <span>{c.title}</span>
                <em>{clock(c.updatedAt)}</em>
              </button>
              <button type="button" className="onto-chat__convo-del" aria-label={`Delete ${c.title}`}
                onClick={() => removeChat(c.id)}><Trash2 size={12} /></button>
            </li>
          ))}
          {!chats.length ? <li className="onto-chat__side-empty">No chats yet</li> : null}
        </ul>
        <button type="button" className={cx('onto-chat__rules-btn', panel === 'rules' && 'is-on')}
          onClick={() => setPanel((p) => p === 'rules' ? 'chat' : 'rules')}>
          <ShieldCheck size={14} aria-hidden="true" /> Business rules
        </button>
      </aside>

      {panel === 'rules' ? (
        <div className="onto-chat__rules">
          <RulesPanel oid={view.id} />
        </div>
      ) : (
        <div className="onto-chat__main">
          <div className="onto-chat__thread" aria-live="polite">
            {!msgs.length && !busy ? (
              <div className="onto-chat__empty">
                <MessageSquarePlus size={28} aria-hidden="true" />
                <h3>Ask this ontology</h3>
                <p>
                  Answers use only <strong>{view.name}</strong> — terms, tables, links, and
                  business rules. For graph, semantic, and context together, open Chat in the sidebar.
                </p>
                {!view.ai.configured ? (
                  <p className="onto-chat__warn">No AI model is configured: explanations and rules still work; SQL answers need a model.</p>
                ) : null}
                <div className="onto-chat__starters">
                  {starters.map((text) => (
                    <button key={text} type="button" disabled={busy} onClick={() => void send(text)}>{text}</button>
                  ))}
                </div>
              </div>
            ) : null}
            {msgs.map((m) => (
              <AskBubble key={m.id} msg={m} />
            ))}
            {busy ? (
              <div className="onto-chat__bubble is-assistant is-thinking">
                <span className="onto-chat__dots" aria-hidden="true"><i /><i /><i /></span>
                <span>Reading the ontology…</span>
              </div>
            ) : null}
            <div ref={end} />
          </div>
          <form className="onto-chat__composer" onSubmit={(e) => { e.preventDefault(); void send(draft) }}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask a Question…"
              aria-label="Ask a question"
              disabled={busy}
            />
            <button type="submit" aria-label="Send" disabled={busy || !draft.trim()}>
              <Send size={16} aria-hidden="true" />
            </button>
          </form>
        </div>
      )}
    </div>
  )
}

function AskCards({ msg }: { msg: AskMsg }) {
  return (
    <div className="onto-chat__bubble is-assistant is-wide">
      <div className="onto-chat__cards">
        {msg.metric ? (
          <div className="onto-chat__card onto-chat__card--metric">
            <header><ShieldCheck size={14} aria-hidden="true" /> Certified metric</header>
            <strong>{msg.metric.title || msg.metric.name}</strong>
            {msg.metric.owner ? <span>Owner {msg.metric.owner}</span> : null}
          </div>
        ) : null}
        {msg.records?.length ? (
          <div className="onto-chat__card onto-chat__card--records">
            <header><Waypoints size={14} aria-hidden="true" /> Matched records</header>
            <ul>
              {msg.records.map((r) => (
                <li key={`${r.set}|${r.key}`}>
                  <b>{r.label}</b>
                  <small>{r.thing}</small>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {msg.facts?.length ? (
          <div className="onto-chat__card onto-chat__card--facts">
            <header>Proven facts</header>
            <ul>
              {msg.facts.slice(0, 6).map((f, i) => (
                <li key={`${f.citation}-${i}`}>
                  <span>{f.text}</span>
                  {f.source ? <small>{f.source}</small> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <time>{clock(msg.stamp)}</time>
    </div>
  )
}

function AskBubble({ msg }: { msg: AskMsg }) {
  const [page, setPage] = useState(0)
  const pageSize = 8
  const isUser = msg.role === 'user'
  const rows = msg.rows ?? []
  const columns = msg.columns ?? []
  const pages = Math.max(1, Math.ceil(rows.length / pageSize))
  const slice = rows.slice(page * pageSize, page * pageSize + pageSize)
  const single = rows.length === 1 && columns.length === 1

  if (msg.kind === 'cards') return <AskCards msg={msg} />

  if (msg.kind === 'results') {
    return (
      <div className="onto-chat__bubble is-assistant is-wide">
        <div className="onto-chat__results">
          <header>
            <span>Query results</span>
            {columns.length ? (
              <button type="button" onClick={() => downloadCsv(columns, rows, `ontology-ask-${msg.stamp}.csv`)}>
                <Download size={13} aria-hidden="true" /> CSV
              </button>
            ) : null}
          </header>
          {single ? (
            <p className="onto-chat__single"><em>{columns[0]}:</em> <strong>{fmtCell(rows[0][0])}</strong></p>
          ) : columns.length ? (
            <>
              <div className="onto-chat__table-wrap">
                <table>
                  <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {slice.map((row, i) => (
                      <tr key={i}>{row.map((v, j) => <td key={j} className={typeof v === 'number' ? 'num' : ''}>{fmtCell(v)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <footer>
                <button type="button" disabled={page <= 0} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">‹</button>
                <span>{page + 1}</span>
                <button type="button" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} aria-label="Next page">›</button>
                <em>{page * pageSize + 1}–{Math.min(rows.length, page * pageSize + pageSize)} out of {rows.length}{msg.truncated ? '+' : ''}</em>
              </footer>
            </>
          ) : <p className="muted">No rows.</p>}
        </div>
        <time>{clock(msg.stamp)}</time>
      </div>
    )
  }

  const wide = Boolean(
    !isUser && (msg.sql || msg.metric || (msg.records?.length ?? 0) > 0 || (msg.facts?.length ?? 0) > 0),
  )

  return (
    <div className={cx('onto-chat__bubble', isUser ? 'is-user' : 'is-assistant', wide && 'is-wide', msg.kind === 'error' && 'is-error')}>
      {msg.content ? <p className="onto-chat__prose">{msg.content}</p> : null}

      {msg.metric ? (
        <div className="onto-chat__card onto-chat__card--metric">
          <header><ShieldCheck size={14} aria-hidden="true" /> Certified metric</header>
          <strong>{msg.metric.title || msg.metric.name}</strong>
          {msg.metric.owner ? <span>Owner {msg.metric.owner}</span> : null}
        </div>
      ) : null}

      {msg.records?.length ? (
        <div className="onto-chat__card onto-chat__card--records">
          <header><Waypoints size={14} aria-hidden="true" /> Matched records</header>
          <ul>
            {msg.records.map((r) => (
              <li key={`${r.set}|${r.key}`}>
                <b>{r.label}</b>
                <small>{r.thing}</small>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {msg.facts?.length ? (
        <div className="onto-chat__card onto-chat__card--facts">
          <header>Proven facts</header>
          <ul>
            {msg.facts.slice(0, 5).map((f, i) => (
              <li key={`${f.citation}-${i}`}>
                <span>{f.text}</span>
                {f.source ? <small>{f.source}</small> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {msg.layers?.length ? (
        <p className="onto-chat__layers">
          {msg.layers.map((l) => l.layer).filter((v, i, a) => a.indexOf(v) === i).join(' · ')}
        </p>
      ) : null}

      {msg.sql ? (
        <div className="onto-chat__sql">
          <header>
            <span>SQL</span>
            <button type="button" aria-label="Copy SQL" onClick={() => void navigator.clipboard.writeText(msg.sql!)}>
              <Copy size={12} aria-hidden="true" /> Copy
            </button>
          </header>
          <pre><code>{msg.sql}</code></pre>
        </div>
      ) : null}
      <time>{clock(msg.stamp)}</time>
    </div>
  )
}

/* ------------------------------------------------------------------- use it */
function UseIt({ view }: { view: View }) {
  const use = useAsync((signal) => api.ontoUse(view.id, signal), [view.id, view.version])
  if (!use.data) return <p className="muted">Loading…</p>
  const u = use.data
  const files: Array<{ href: string; label: string; hint: string; icon: typeof FileJson; download?: boolean; name?: string }> = [
    { href: u.files.json, label: 'JSON', hint: 'Things, fields, and links as tables', icon: FileJson },
    { href: u.files.model, label: 'Strata Model', hint: 'Open JSON for any copy of the data', icon: FileJson, download: true, name: `${view.id}.strata-model.json` },
    { href: u.files.ossie, label: 'Apache Ossie', hint: 'Semantic-layer interchange', icon: FileJson, download: true, name: `${view.id}.ossie.yaml` },
    { href: u.files.owl, label: 'OWL / Turtle', hint: 'Standard ontology format', icon: Share2 },
    { href: u.files.shacl, label: 'SHACL', hint: 'Data quality rules', icon: CircleCheck },
    { href: u.files.git_zip, label: 'Git folder', hint: 'Ontology as code (.zip)', icon: GitBranch, download: true, name: `${view.id}-ontology.zip` },
  ]
  return (
    <div className="onto-use onto-use--clean">
      <header className="onto-use__intro">
        <h2>Use it</h2>
        <p>Export this ontology or wire it into your own system. Everything here is from <strong>{view.name}</strong> only.</p>
      </header>
      <section className="onto-use__card onto-use__card--files" aria-label="Files">
        <div className="onto-use__card-head">
          <span className="onto-use__icon"><FileJson size={18} aria-hidden="true" /></span>
          <div>
            <h3>Files</h3>
            <p>Download standard formats for tools and Git.</p>
          </div>
        </div>
        <ul className="onto-use__files">
          {files.map((f) => {
            const Icon = f.icon
            return (
              <li key={f.label}>
                {f.download ? (
                  <DownloadLink href={f.href} fallback={f.name || f.label}><Icon size={15} aria-hidden="true" /> {f.label}</DownloadLink>
                ) : (
                  <a href={f.href} target="_blank" rel="noreferrer"><Icon size={15} aria-hidden="true" /> {f.label}</a>
                )}
                <span>{f.hint}</span>
              </li>
            )
          })}
        </ul>
      </section>
      <div className="onto-use__wide">
        <UseElsewhere layer="ontology" oid={view.id} open />
      </div>
    </div>
  )
}
