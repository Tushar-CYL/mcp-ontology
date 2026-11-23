import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CircleCheck, HelpCircle, X } from 'lucide-react'
import { api, describeError } from '../../api/client'
import type { CtxGapGroup, CtxGaps } from '../../api/types'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'

/** Questions the Context page or an agent could not answer, grouped and
 *  ranked, each with the fix a person can apply. */
export function Gaps({ oid, refresh }: { oid: string; refresh: number }) {
  const state = useAsync<CtxGaps>((signal) => api.ctxGaps(oid, signal), [oid])
  const [data, setData] = useState<CtxGaps | null>(null)
  const { reload } = state
  useEffect(() => {
    if (refresh) {
      setData(null)
      reload()
    }
  }, [refresh, reload])
  const view = data ?? state.data
  if (!view) return null
  return (
    <Card className="gaps" title={<><HelpCircle size={18} aria-hidden="true" /> Questions it could not answer</>}
      subtitle="Every question the Context page or an agent could not answer, grouped and counted. Fix the top ones and the answers improve for everyone.">
      {view.groups.length ? (
        <ul className="gaps__list">
          {view.groups.map((g) => <GapRow key={g.key} oid={oid} g={g} onChange={setData} />)}
        </ul>
      ) : (
        <p className="gaps__none"><CircleCheck size={16} aria-hidden="true" /> Nothing yet: every question so far was answered.</p>
      )}
    </Card>
  )
}

function GapRow({ oid, g, onChange }: { oid: string; g: CtxGapGroup; onChange: (next: CtxGaps) => void }) {
  const toast = useToast()
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const dismiss = async (said?: string) => {
    try {
      onChange(await api.ctxGapDismiss(oid, g.key))
      if (said) toast.push({ title: said, tone: 'success' })
    } catch (e) {
      toast.push({ title: 'Could not update the list', message: describeError(e).message, tone: 'error' })
    }
  }
  const saveNote = async () => {
    if (!note?.trim()) return
    setBusy(true)
    try {
      await api.ontoContext(oid, note.trim())
      await dismiss('Saved as context. Every layer uses it now.')
      setNote(null)
    } catch (e) {
      toast.push({ title: 'Could not save the note', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <li className="gap">
      <div className="gap__head">
        <span className="gap__count" title="Times asked">{g.count}×</span>
        <strong className="gap__q">{g.question}</strong>
        <button type="button" className="gap__x" aria-label="Dismiss" onClick={() => void dismiss()}><X size={14} /></button>
      </div>
      <p className="gap__why">{g.label}{g.detail ? `: ${g.detail}` : ''}</p>
      <p className="gap__meta">Asked on {g.sources.map((s) => s.replace(/^agent:/, 'agent ')).join(', ')}{g.things.length ? ` · about ${g.things.slice(0, 3).join(', ')}` : ''}</p>
      <div className="gap__fix">
        <span><ArrowRight size={13} aria-hidden="true" /> {g.fix.text}</span>
        {g.fix.action === 'metric' ? (
          <Link className="btn btn--secondary btn--sm" to={`/tools/semantic/${encodeURIComponent(oid)}`}>Open Semantic</Link>
        ) : null}
        {note === null ? (
          <Button size="sm" variant="secondary" onClick={() => setNote(g.fix.note || '')}>Add as context</Button>
        ) : null}
      </div>
      {note !== null ? (
        <form className="gap__note" onSubmit={(e) => { e.preventDefault(); void saveNote() }}>
          <input className="input" autoFocus value={note} maxLength={4000} aria-label="Note"
            onChange={(e) => setNote(e.target.value)} />
          <Button type="submit" size="sm" variant="primary" loading={busy} disabled={!note.trim()}>Save</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setNote(null)}>Cancel</Button>
        </form>
      ) : null}
    </li>
  )
}
