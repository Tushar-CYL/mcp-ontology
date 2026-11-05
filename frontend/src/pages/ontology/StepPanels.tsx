import { useState, type ReactNode } from 'react'
import { Download, GitBranch, Radar, Search, ShieldCheck, UserPlus } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { EoDiff, EoDrift, EoEntity, EoItem, EoState } from '../../api/types'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Callout } from '../../components/Callout'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Select, TextInput } from '../../components/Field'
import { LoadingState } from '../../components/LoadingState'
import { Table } from '../../components/Table'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { findingInfo, groupBy, isMoneyProperty, methodLabel, pct, ROLE_LABEL } from '../../utils/eo'
import { formatNumber } from '../../utils/format'
import { BulkApprove, Evidence, ItemActions } from './shared'

type Payload = Record<string, any>  // eslint-disable-line @typescript-eslint/no-explicit-any

export interface PanelProps {
  oid: string
  state: EoState
  by: string
  onChanged: () => void
}

function useItems(oid: string, kind: string, tick: number) {
  return useAsync((signal) => api.eoItems<Payload>(oid, kind, signal), [oid, kind, tick])
}

function Loaded<T>({ result, children }: {
  result: { data: T | undefined; error: unknown; initialLoading: boolean; reload: () => void }
  children: (data: T) => ReactNode
}) {
  if (result.initialLoading) return <LoadingState compact label="Loading" />
  if (result.error) return <ErrorState compact error={result.error} onRetry={result.reload} />
  if (result.data === undefined) return null
  return <>{children(result.data)}</>
}

function FindingList({ state, types }: { state: EoState; types: string[] }) {
  const list = state.findings.filter((f) => types.includes(f.type))
  if (!list.length) return null
  return (
    <div className="stack">
      {list.map((f) => (
        <Callout key={f.key} tone={findingInfo(f.type).tone === 'rose' ? 'danger' : 'warning'}
          title={findingInfo(f.type).title}>{f.detail}</Callout>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- intake
export function IntakePanel({ state }: PanelProps) {
  const o = state.ontology
  return (
    <Card title="Intake" subtitle="The problem and the sources, as the team described them.">
      <div className="stack">
        <p>{o.problem || <span className="muted">No problem statement given.</span>}</p>
        {o.questions.length ? (
          <div>
            <p className="field__label">Business questions</p>
            <ul className="eo-list">{o.questions.map((q) => <li key={q}>{q}</li>)}</ul>
          </div>
        ) : null}
        <Table dense rows={o.sources} rowKey={(s) => s.source_id} columns={[
          { key: 's', header: 'Source', render: (s) => <span className="code">{s.source_id}</span> },
          { key: 'r', header: 'Role', render: (s) => ROLE_LABEL[s.role] ?? s.role },
          { key: 'o', header: 'Owner team', render: (s) => s.owner_team || '-' },
          { key: 'c', header: 'Refresh SLA', align: 'right', render: (s) => `${s.cadence_days} day(s)` },
        ]} />
      </div>
    </Card>
  )
}

// --------------------------------------------------------------- profile
export function ProfilePanel({ oid }: PanelProps) {
  const result = useItems(oid, 'profile', 0)
  const [open, setOpen] = useState<string | null>(null)
  return (
    <Card title="Connect and profile" subtitle="Every column measured: the evidence every proposal cites.">
      <Loaded result={result}>{({ items }) => {
        const chosen = items.find((i) => i.key === open)
        return (
          <div className="stack">
            <Table dense rows={items} rowKey={(i) => i.key} columns={[
              { key: 't', header: 'Table', render: (i) => (
                <button type="button" className="link-button" onClick={() => setOpen(i.key)}>{i.key}</button>) },
              { key: 'r', header: 'Rows', align: 'right', render: (i) => formatNumber(i.payload.rows) },
              { key: 'c', header: 'Columns', align: 'right', render: (i) => i.payload.columns.length },
              { key: 'f', header: 'Latest date', render: (i) => i.payload.freshness ?? '-' },
            ]} />
            {chosen ? (
              <Table dense caption={chosen.key} rows={chosen.payload.columns as Payload[]} rowKey={(c) => c.name}
                columns={[
                  { key: 'n', header: 'Column', render: (c) => <span className="code">{c.name}</span> },
                  { key: 'f', header: 'Type', render: (c) => c.family },
                  { key: 'u', header: 'Nulls', align: 'right', render: (c) => pct(c.null_ratio, 1) },
                  { key: 'd', header: 'Distinct', align: 'right', render: (c) => formatNumber(c.distinct) },
                  { key: 'v', header: 'Range / top values', render: (c) => c.min !== undefined
                    ? `${c.min ?? '-'} .. ${c.max ?? '-'}`
                    : (c.top_values as Payload[]).slice(0, 4).map((t) => `${t.value} (${t.count})`).join(', ') || '-' },
                ]} />
            ) : <p className="muted">Pick a table to see its columns.</p>}
          </div>
        )
      }}</Loaded>
    </Card>
  )
}

// -------------------------------------------------------------- concepts
export function ConceptsPanel({ oid, state, by, onChanged }: PanelProps) {
  const [tick, setTick] = useState(0)
  const result = useItems(oid, 'concept', tick)
  const done = () => { setTick((t) => t + 1); onChanged() }
  return (
    <Card title="Shared concepts" subtitle="Tables in different systems that are one business thing."
      actions={result.data ? <BulkApprove oid={oid} kind="concept" by={by} items={result.data.items} onDone={done} /> : null}>
      <FindingList state={state} types={['duplicate_business_key']} />
      <Loaded result={result}>{({ items }) => (
        <div className="eo-concepts">
          {items.map((item) => (
            <article key={item.key} className="eo-concept">
              <header className="eo-concept__head">
                <h3>{item.key}</h3>
                {item.payload.tier ? <Badge tone={item.payload.tier === 'core' ? 'indigo' : 'slate'}>{item.payload.tier}</Badge> : null}
                <span className="muted">{pct(item.confidence)} confident</span>
              </header>
              <p>{item.payload.description}</p>
              <div className="chip-row">
                {(item.payload.members as string[]).map((m) => (
                  <Badge key={m} tone={m === item.payload.master ? 'amber' : 'neutral'}>
                    {m}{m === item.payload.master ? ' (master)' : ''}
                  </Badge>
                ))}
              </div>
              <Evidence lines={item.evidence} max={3} />
              <ItemActions oid={oid} item={item} by={by} onDone={done} />
            </article>
          ))}
        </div>
      )}</Loaded>
    </Card>
  )
}

// --------------------------------------------------------------- mapping
export function MappingPanel({ oid, state, by, onChanged }: PanelProps) {
  const toast = useToast()
  const [tick, setTick] = useState(0)
  const [moneyOnly, setMoneyOnly] = useState(true)
  const [editing, setEditing] = useState<EoItem<Payload> | null>(null)
  const [draft, setDraft] = useState({ property: '', definition: '' })
  const result = useItems(oid, 'mapping', tick)
  const done = () => { setTick((t) => t + 1); onChanged() }
  const startEdit = (item: EoItem<Payload>) => {
    setEditing(item)
    setDraft({ property: item.payload.property, definition: item.payload.definition ?? '' })
  }
  const saveEdit = async () => {
    if (!editing) return
    try {
      await api.eoDecide(oid, { kind: 'mapping', key: editing.key, decision: 'edited', by,
        payload: { ...editing.payload, property: draft.property.trim(), definition: draft.definition.trim() } })
      setEditing(null)
      done()
    } catch (error) {
      toast.push({ title: 'Not saved', message: describeError(error).message, tone: 'error' })
    }
  }
  return (
    <Card title="Properties with meaning"
      subtitle="Every column gets a defined property and unit, from its name, its arithmetic, and other systems."
      actions={result.data ? <BulkApprove oid={oid} kind="mapping" by={by} items={result.data.items}
        minConfidence={0.9} label="Approve confident" onDone={done} /> : null}>
      <div className="stack">
        <FindingList state={state} types={['wrong_amount_column', 'mixed_currency_total', 'name_contradicts_values']} />
        <label className="cell-inline">
          <input type="checkbox" checked={moneyOnly} onChange={(e) => setMoneyOnly(e.target.checked)} />
          Money columns only
        </label>
        <Loaded result={result}>{({ items }) => {
          const shown = items.filter((i) => !moneyOnly || isMoneyProperty(String(i.payload.property)))
          return groupBy(shown, (i) => i.payload.table).map(([table, rows]) => (
            <Table key={table} dense caption={table} rows={rows} rowKey={(i) => i.key} columns={[
              { key: 'c', header: 'Column', render: (i) => <span className="code">{i.payload.column}</span> },
              { key: 'p', header: 'Means', render: (i) => (
                <span title={i.payload.definition}><Badge tone={i.payload.property === 'amount_unclassified' ? 'rose' : 'indigo'}>{i.payload.property}</Badge></span>) },
              { key: 'm', header: 'How we know', render: (i) => (
                <span title={i.evidence.join('\n')}>{methodLabel(i.payload.method)}</span>) },
              { key: 'k', header: 'Confidence', align: 'right', render: (i) => pct(i.confidence) },
              { key: 'u', header: 'Unit', render: (i) => i.payload.unit ?? '-' },
              { key: 'a', header: '', render: (i) => (
                <ItemActions oid={oid} item={i} by={by} onDone={done} onEdit={() => startEdit(i)} />) },
            ]} />
          ))
        }}</Loaded>
        {editing ? (
          <div className="eo-edit" role="dialog" aria-label={`Edit ${editing.key}`}
            ref={(node) => node?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>
            <p className="cell-title">{editing.key}</p>
            <TextInput label="Property" value={draft.property}
              onChange={(e) => setDraft({ ...draft, property: e.target.value })} />
            <TextInput label="Definition" value={draft.definition}
              onChange={(e) => setDraft({ ...draft, definition: e.target.value })} />
            <div className="form-actions">
              <Button variant="primary" onClick={saveEdit} disabled={!draft.property.trim()}>Save and approve</Button>
              <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  )
}

// ------------------------------------------------------------- structure
export function StructurePanel({ oid, by, onChanged }: PanelProps) {
  const [tick, setTick] = useState(0)
  const rels = useItems(oid, 'relationship', tick)
  const hier = useItems(oid, 'hierarchy', tick)
  const done = () => { setTick((t) => t + 1); onChanged() }
  return (
    <div className="panel-stack">
      <Card title="Relationships" subtitle="Measured, not assumed: how many children per parent, and how many find one."
        actions={rels.data ? <BulkApprove oid={oid} kind="relationship" by={by} items={rels.data.items} onDone={done} /> : null}>
        <Loaded result={rels}>{({ items }) => (
          <Table dense rows={items} rowKey={(i) => i.key} columns={[
            { key: 'l', header: 'Link', render: (i) => <span className="cell-title">{i.payload.from_concept} → {i.payload.to_concept}</span> },
            { key: 'v', header: 'Through', render: (i) => <span className="code">{i.payload.from} → {i.payload.to}</span> },
            { key: 'c', header: 'Cardinality', render: (i) => i.payload.cardinality ?? '-' },
            { key: 'r', header: 'Required', render: (i) => (i.payload.required ? 'yes' : 'no') },
            { key: 'm', header: 'Children matched', align: 'right', render: (i) => pct(i.payload.matched, 1) },
            { key: 'u', header: 'Parents used', align: 'right', render: (i) => pct(i.payload.parents_used, 1) },
            { key: 'a', header: '', render: (i) => <ItemActions oid={oid} item={i} by={by} onDone={done} /> },
          ]} />
        )}</Loaded>
      </Card>
      <Card title="Hierarchies" subtitle="Drill paths found from the data: each child value sits under exactly one parent.">
        <Loaded result={hier}>{({ items }) => items.length ? (
          <div className="stack">
            {items.map((i) => (
              <div key={i.key} className="eo-hierarchy">
                <p className="cell-title">{i.payload.concept}: {(i.payload.levels as string[]).join(' > ')}</p>
                <div className="chip-row">
                  {Object.entries(i.payload.parent_of as Record<string, string>).slice(0, 14).map(([c, p]) => (
                    <Badge key={c} tone="neutral">{p} › {c}</Badge>))}
                </div>
                <Evidence lines={i.evidence} />
                <ItemActions oid={oid} item={i} by={by} onDone={done} />
              </div>
            ))}
          </div>
        ) : <p className="muted">No hierarchy in this data.</p>}</Loaded>
      </Card>
    </div>
  )
}

// -------------------------------------------------------------- identity
export function IdentityPanel({ oid, state }: PanelProps) {
  const result = useItems(oid, 'identity', 0)
  const [value, setValue] = useState('')
  const [entity, setEntity] = useState<EoEntity | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const resolve = async () => {
    setBusy(true)
    setError(null)
    try {
      setEntity(await api.eoResolve(oid, value.trim()))
    } catch (cause) {
      setEntity(null)
      setError(cause)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="panel-stack">
      <Card title="Identity across sources" subtitle="Which records in which systems are one entity. Nothing is merged in the sources.">
        <div className="stack">
          <FindingList state={state} types={['duplicate_golden_record']} />
          <Loaded result={result}>{({ items }) => (
            <Table dense rows={items} rowKey={(i) => i.key} columns={[
              { key: 'c', header: 'Concept', render: (i) => <span className="cell-title">{i.key}</span> },
              { key: 'r', header: 'Records', align: 'right', render: (i) => formatNumber(i.payload.records) },
              { key: 'e', header: 'Entities', align: 'right', render: (i) => formatNumber(i.payload.entities) },
              { key: 'l', header: 'In 2+ systems', align: 'right', render: (i) => formatNumber(i.payload.linked_entities) },
              { key: 'm', header: 'How', render: (i) => Object.entries(i.payload.methods as Record<string, number>)
                .map(([k, v]) => `${k} ${formatNumber(v)}`).join(' · ') },
            ]} />
          )}</Loaded>
        </div>
      </Card>
      <Card title="Look up one entity" subtitle="Type any system's id: the CRM account, ERP customer, billing reference or golden id.">
        <div className="stack">
          <form className="form-row" onSubmit={(e) => { e.preventDefault(); if (value.trim()) void resolve() }}>
            <TextInput label="Any id" value={value} placeholder="e.g. B-5000 or 100000"
              onChange={(e) => setValue(e.target.value)} />
            <Button type="submit" icon={<Search size={15} />} loading={busy} disabled={!value.trim()}>Resolve</Button>
          </form>
          {error ? <ErrorState compact error={error} /> : null}
          {entity ? (
            <div className="grid-2">
              <Table dense caption={`${entity.concept} ${entity.entity_id}: records`}
                rows={Object.entries(entity.records)} rowKey={([t]) => t} columns={[
                  { key: 't', header: 'System table', render: ([t]) => <span className="code">{t}</span> },
                  { key: 'r', header: 'Record', render: ([, r]) => r.join(', ') },
                  { key: 'm', header: 'Matched by', render: ([t, r]) => entity.methods[`${t}.${r[0]}`]?.method ?? '-' },
                ]} />
              <Table dense caption="Golden record (by survivorship rules)"
                rows={Object.entries(entity.golden)} rowKey={([p]) => p} columns={[
                  { key: 'p', header: 'Property', render: ([p]) => p },
                  { key: 'v', header: 'Value', render: ([, g]) => String(g.value) },
                  { key: 's', header: 'From', render: ([, g]) => <span className="code">{g.source}</span> },
                ]} />
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------- survivorship
export function SurvivorshipPanel({ oid, state, by, onChanged }: PanelProps) {
  const [tick, setTick] = useState(0)
  const fresh = useItems(oid, 'freshness', tick)
  const conflicts = useItems(oid, 'conflict', tick)
  const rules = useItems(oid, 'survivorship', tick)
  const done = () => { setTick((t) => t + 1); onChanged() }
  return (
    <div className="panel-stack">
      <Card title="Freshness against each source's SLA">
        <FindingList state={state} types={['stale_source']} />
        <Loaded result={fresh}>{({ items }) => (
          <Table dense rows={items} rowKey={(i) => i.key} columns={[
            { key: 's', header: 'Source', render: (i) => <span className="code">{i.key}</span> },
            { key: 'r', header: 'Role', render: (i) => ROLE_LABEL[i.payload.role] ?? i.payload.role },
            { key: 'l', header: 'Latest', render: (i) => i.payload.latest },
            { key: 'g', header: 'Behind', align: 'right', render: (i) => `${i.payload.lag_days} d` },
            { key: 'a', header: 'SLA', align: 'right', render: (i) => `${i.payload.sla_days} d` },
            { key: 'b', header: '', render: (i) => (i.payload.breach
              ? <Badge tone="rose" dot>Breach</Badge> : <Badge tone="teal" dot>On time</Badge>) },
          ]} />
        )}</Loaded>
      </Card>
      <Card title="Where systems disagree" subtitle="Compared through the identity crosswalk, after normalising case and punctuation.">
        <FindingList state={state} types={['corrections_not_in_sources']} />
        <Loaded result={conflicts}>{({ items }) => (
          <div className="stack">
            {items.map((i) => (
              <div key={i.key}>
                <p className="cell-title">{i.key}: {formatNumber(i.payload.entities_in_conflict)} of {formatNumber(i.payload.entities_compared)} disagree</p>
                {(i.payload.examples as Payload[]).slice(0, 3).map((ex) => (
                  <p key={ex.entity_id} className="muted eo-example">
                    <Badge tone={ex.kind === 'hub_override' ? 'amber' : 'rose'}>{ex.kind === 'hub_override' ? 'corrected in hub' : 'sources disagree'}</Badge>{' '}
                    {Object.entries(ex.values as Record<string, string>).map(([s, v]) => `${s.split('.')[0]}: ${v}`).join(' | ')}
                  </p>
                ))}
              </div>
            ))}
          </div>
        )}</Loaded>
      </Card>
      <Card title="Which source wins" subtitle="Proposed survivorship rules, with reasons."
        actions={rules.data ? <BulkApprove oid={oid} kind="survivorship" by={by} items={rules.data.items} onDone={done} /> : null}>
        <Loaded result={rules}>{({ items }) => (
          <Table dense rows={items} rowKey={(i) => i.key} columns={[
            { key: 'p', header: 'Property', render: (i) => <span className="code">{i.key}</span> },
            { key: 'r', header: 'Rule', render: (i) => i.payload.rule.replace(/_/g, ' ') },
            { key: 'w', header: 'Winner', render: (i) => i.payload.winner ?? 'majority' },
            { key: 'y', header: 'Why', render: (i) => (
              <span>{i.payload.reason}{i.payload.caveat ? <span className="eo-caveat"> Caveat: {i.payload.caveat}</span> : null}</span>) },
            { key: 'a', header: '', render: (i) => <ItemActions oid={oid} item={i} by={by} onDone={done} /> },
          ]} />
        )}</Loaded>
      </Card>
    </div>
  )
}

// ----------------------------------------------------------------- rules
export function RulesPanel({ oid, by, onChanged }: PanelProps) {
  const [tick, setTick] = useState(0)
  const rules = useItems(oid, 'rule', tick)
  const actions = useItems(oid, 'action', tick)
  const done = () => { setTick((t) => t + 1); onChanged() }
  return (
    <div className="panel-stack">
      <Card title="Validation rules" subtitle="Derived from what the data proved, checked live. Each carries the SQL behind it."
        actions={rules.data ? <BulkApprove oid={oid} kind="rule" by={by} items={rules.data.items} onDone={done} /> : null}>
        <Loaded result={rules}>{({ items }) => (
          <div className="stack">
            {items.map((i) => (
              <div key={i.key} className="eo-rule">
                <div className="eo-rule__head">
                  <Badge tone={i.payload.violations ? (i.payload.severity === 'error' ? 'rose' : 'amber') : 'teal'} dot>
                    {i.payload.violations ? `${formatNumber(i.payload.violations)} violation(s)` : 'Holds'}
                  </Badge>
                  <span>{i.payload.description}</span>
                </div>
                {i.payload.offending?.length ? (
                  <div className="chip-row">{(i.payload.offending as Payload[]).map((o) => (
                    <Badge key={o.value} tone="neutral" title={o.label}>{o.value} × {o.count} ({o.label})</Badge>))}</div>
                ) : null}
                {i.payload.blank ? <p className="muted">{formatNumber(i.payload.blank)} blank value(s), counted as missing</p> : null}
                {i.payload.sample?.length ? <p className="muted">e.g. {(i.payload.sample as string[]).slice(0, 6).join(', ')}</p> : null}
                <details><summary>SQL</summary><pre className="code">{i.payload.sql}</pre></details>
                <ItemActions oid={oid} item={i} by={by} onDone={done} />
              </div>
            ))}
          </div>
        )}</Loaded>
      </Card>
      <Card title="Action types" subtitle="What an agent may propose. Nothing executes without the named approver."
        actions={actions.data ? <BulkApprove oid={oid} kind="action" by={by} items={actions.data.items} onDone={done} /> : null}>
        <Loaded result={actions}>{({ items }) => (
          <Table dense rows={items} rowKey={(i) => i.key} columns={[
            { key: 'n', header: 'Action', render: (i) => <span className="code">{i.key}</span> },
            { key: 'd', header: 'What it does', render: (i) => i.payload.description },
            { key: 'p', header: 'Proposed now', align: 'right', render: (i) => (i.payload.proposed as unknown[]).length },
            { key: 'w', header: 'Approver', render: (i) => i.payload.approver || '-' },
            { key: 'a', header: '', render: (i) => <ItemActions oid={oid} item={i} by={by} onDone={done} /> },
          ]} />
        )}</Loaded>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------- govern
export function GovernPanel({ oid, state, onChanged }: PanelProps) {
  const toast = useToast()
  const [user, setUser] = useState('')
  const [role, setRole] = useState<'viewer' | 'editor' | 'approver'>('approver')
  const [busy, setBusy] = useState(false)
  const audit = useAsync((signal) => api.eoAudit(oid, signal), [oid, state.roles.length])
  const owners = async () => {
    setBusy(true)
    try {
      await api.eoOwners(oid)
      toast.push({ title: 'Owners assigned', tone: 'success' })
      onChanged()
    } catch (error) {
      toast.push({ title: 'Not assigned', message: describeError(error).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  const grant = async () => {
    try {
      await api.eoGrant(oid, user.trim(), role)
      setUser('')
      onChanged()
    } catch (error) {
      toast.push({ title: 'Not granted', message: describeError(error).message, tone: 'error' })
    }
  }
  return (
    <div className="panel-stack">
      <Card title="Ownership" subtitle="Shared concepts are core, owned by governance; single-system concepts are extensions owned by that team."
        actions={<Button size="sm" variant="primary" icon={<ShieldCheck size={14} />} loading={busy} onClick={owners}>Assign owners</Button>}>
        <p className="muted">Owners come from the intake: the MDM hub's team for core concepts, each system's team for its own.</p>
      </Card>
      <Card title="Roles" subtitle="Until someone is granted a role, the first steward bootstraps. After that only approvers decide and publish.">
        <div className="stack">
          {state.roles.length ? (
            <div className="chip-row">{state.roles.map((r) => <Badge key={r.user} tone="indigo">{r.user}: {r.role}</Badge>)}</div>
          ) : <p className="muted">No roles yet.</p>}
          <div className="form-row">
            <TextInput label="User" value={user} onChange={(e) => setUser(e.target.value)} />
            <Select label="Role" value={role} onValueChange={(v) => setRole(v as typeof role)}
              options={[{ value: 'viewer', label: 'Viewer' }, { value: 'editor', label: 'Editor' }, { value: 'approver', label: 'Approver' }]} />
            <Button icon={<UserPlus size={15} />} onClick={grant} disabled={!user.trim()}>Grant</Button>
          </div>
        </div>
      </Card>
      <Card title="Audit trail" subtitle="Every decision, who made it and when.">
        <Loaded result={audit}>{({ audit: rows }) => (
          <Table dense maxHeight={320} rows={[...rows].reverse().slice(0, 100)} rowKey={(r, i) => `${r.at}-${i}`} columns={[
            { key: 'w', header: 'When', render: (r) => r.at.replace('T', ' ').slice(0, 16) },
            { key: 'b', header: 'Who', render: (r) => r.by },
            { key: 'd', header: 'Decision', render: (r) => r.decision },
            { key: 'k', header: 'Item', render: (r) => <span className="code">{r.kind}: {r.key}</span> },
            { key: 'n', header: 'Note', render: (r) => r.note || '-' },
          ]} />
        )}</Loaded>
      </Card>
    </div>
  )
}

// --------------------------------------------------------------- publish
export function PublishPanel({ oid, state, by, onChanged }: PanelProps) {
  const toast = useToast()
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [diff, setDiff] = useState<EoDiff | null>(null)
  const versions = state.versions
  const latest = versions[versions.length - 1]
  const [a, setA] = useState(versions.length > 1 ? versions[versions.length - 2].version : 1)
  const publish = async () => {
    setBusy(true)
    try {
      const v = await api.eoPublish(oid, by, notes.trim())
      toast.push({ title: `Published version ${v.version}`, tone: 'success' })
      setNotes('')
      onChanged()
    } catch (error) {
      toast.push({ title: 'Not published', message: describeError(error).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  const showDiff = async () => {
    if (!latest) return
    try {
      setDiff(await api.eoDiff(oid, a, latest.version))
    } catch (error) {
      toast.push({ title: 'No diff', message: describeError(error).message, tone: 'error' })
    }
  }
  return (
    <div className="panel-stack">
      <Card title="Publish a version" subtitle="Approved items freeze into a numbered version, with a data contract per source table.">
        <div className="form-row">
          <TextInput label="Release notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <Button variant="primary" icon={<GitBranch size={15} />} loading={busy} onClick={publish}>Publish</Button>
        </div>
      </Card>
      {latest ? (
        <>
          <Card title="Versions">
            <div className="stack">
              <Table dense rows={[...versions].reverse()} rowKey={(v) => String(v.version)} columns={[
                { key: 'v', header: 'Version', render: (v) => <span className="cell-title">v{v.version}</span> },
                { key: 'w', header: 'Published', render: (v) => v.published_at.replace('T', ' ').slice(0, 16) },
                { key: 'b', header: 'By', render: (v) => v.by },
                { key: 'n', header: 'Notes', render: (v) => v.notes || '-' },
              ]} />
              {versions.length > 1 ? (
                <div className="form-row">
                  <Select label="Compare from" value={String(a)} onValueChange={(v) => setA(Number(v))}
                    options={versions.slice(0, -1).map((v) => ({ value: String(v.version), label: `v${v.version}` }))} />
                  <Button onClick={showDiff}>Show changes to v{latest.version}</Button>
                </div>
              ) : null}
              {diff ? (
                <ul className="eo-list">
                  {(['added', 'changed', 'removed'] as const).flatMap((label) => diff[label].map((d) => (
                    <li key={`${label}-${d.kind}-${d.key}`}><Badge tone={label === 'removed' ? 'rose' : label === 'added' ? 'teal' : 'amber'}>{label}</Badge> {d.kind} <span className="code">{d.key}</span></li>)))}
                  {!diff.added.length && !diff.changed.length && !diff.removed.length ? <li className="muted">No differences.</li> : null}
                </ul>
              ) : null}
            </div>
          </Card>
          <Card title="Where the ontology lives" subtitle="One version, three places.">
            <div className="stack">
              <div className="chip-row">
                <a className="button button--secondary button--sm" href={api.eoExportUrl(oid, 'turtle')} download><Download size={14} /> OWL / Turtle</a>
                <a className="button button--secondary button--sm" href={api.eoExportUrl(oid, 'shacl')} download><Download size={14} /> SHACL shapes</a>
                <a className="button button--secondary button--sm" href={api.eoExportUrl(oid, 'zip')} download><Download size={14} /> Git folder (zip)</a>
              </div>
              <ul className="eo-list">
                <li><strong>The registry</strong>: proposals, decisions, owners and the audit trail; version v{latest.version} is current.</li>
                <li><strong>Your Git repo</strong>: unzip the folder into a repository, so every change is reviewed in a pull request.</li>
                <li><strong>Live</strong>: agents and tools (Context, Semantic, Copilot, Databricks, Snowflake) read the pinned version
                  over MCP (<span className="code">list_concepts, get_concept, map_column, resolve_entity, get_contract, validate_rules, ontology_version</span>)
                  or REST at <span className="code">/api/eo/{oid}</span>. They never read the raw tables.</li>
              </ul>
            </div>
          </Card>
        </>
      ) : <Callout tone="info">Nothing published yet. Approve the proposals you agree with, assign owners, then publish.</Callout>}
    </div>
  )
}

// ----------------------------------------------------------------- drift
export function DriftPanel({ oid, state, onChanged }: PanelProps) {
  const toast = useToast()
  const [tick, setTick] = useState(0)
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState<EoDrift | null>(null)
  const items = useItems(oid, 'drift', tick)
  const check = async () => {
    setBusy(true)
    try {
      setLast(await api.eoDrift(oid))
      setTick((t) => t + 1)
      onChanged()
    } catch (error) {
      toast.push({ title: 'Drift not checked', message: describeError(error).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card title="Drift watch" subtitle="Sources are compared with the contracts of the published version. Changes become proposals; nothing is applied."
      actions={<Button size="sm" variant="primary" icon={<Radar size={14} />} loading={busy}
        disabled={!state.versions.length} onClick={check}>Check drift now</Button>}>
      <div className="stack">
        {!state.versions.length ? <Callout tone="info">Publish a version first: drift is measured against its contracts.</Callout> : null}
        {last ? <p className="muted">Checked {last.checked_at.replace('T', ' ').slice(0, 16)} against v{last.version}: {last.changes.length} change(s).</p> : null}
        <Loaded result={items}>{({ items: rows }) => {
          const changes = rows.filter((r) => r.key !== '_last_check')
          return changes.length ? (
            <Table dense rows={changes} rowKey={(r) => r.key} columns={[
              { key: 't', header: 'Change', render: (r) => <Badge tone={r.payload.type === 'usage_gap' ? 'indigo' : 'amber'}>{String(r.payload.type).replace(/_/g, ' ')}</Badge> },
              { key: 'd', header: 'What', render: (r) => r.payload.detail },
              { key: 's', header: 'Suggested', render: (r) => r.payload.suggestion },
            ]} />
          ) : <p className="muted">No drift recorded.</p>
        }}</Loaded>
      </div>
    </Card>
  )
}
