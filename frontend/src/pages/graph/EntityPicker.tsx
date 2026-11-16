import { useState } from 'react'
import { Search, X } from 'lucide-react'
import { api } from '../../api/client'
import type { KgHit } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useSuggestions } from '../../hooks/useSuggestions'

/** Find an entity by id or name; shows matches as you type. */
export function EntityPicker({ oid, label, placeholder, onPick, autoFocus }: {
  oid: string
  label: string
  placeholder?: string
  onPick: (hit: KgHit) => void
  autoFocus?: boolean
}) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const q = useDebouncedValue(text.trim(), 300)
  const found = useAsync((signal) => api.kgSearch(oid, q, signal), [oid, q], { enabled: q.length > 0 })
  const hits = q ? found.data?.results ?? [] : []
  // Real values from this data to try, before anything is typed.
  const tries = useSuggestions(open ? oid : null, 'search', 0, false)

  const pick = (hit: KgHit) => {
    setText(hit.label ?? hit.key)
    setOpen(false)
    onPick(hit)
  }

  return (
    <div className="kg-picker">
      <div className="kg-picker__box">
        <Search size={15} aria-hidden="true" />
        <input value={text} aria-label={label} placeholder={placeholder ?? 'Search by id or name'}
          autoFocus={autoFocus}
          onChange={(e) => { setText(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => { if (e.key === 'Enter' && hits[0]) pick(hits[0]); if (e.key === 'Escape') setOpen(false) }} />
        {text ? <button type="button" aria-label="Clear" onClick={() => { setText(''); setOpen(false) }}><X size={14} /></button> : null}
      </div>
      {open && !q && tries.items.length ? (
        <ul className="kg-picker__list" aria-label={`${label} suggestions`}>
          <li className="kg-picker__note">Try a value from your data:</li>
          {tries.items.map((t) => (
            <li key={t.text}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => setText(t.text)}>
                <span className="kg-picker__name">{t.text}</span>
                <span className="kg-picker__meta">{t.why}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {open && q ? (
        <ul className="kg-picker__list" role="listbox" aria-label={`${label} results`}>
          {found.loading && !hits.length ? <li className="kg-picker__note">Searching...</li> : null}
          {!found.loading && !hits.length ? <li className="kg-picker__note">Nothing matches "{q}".</li> : null}
          {hits.map((h) => (
            <li key={`${h.set}|${h.key}`} role="option" aria-selected="false">
              <button type="button" onClick={() => pick(h)}>
                <span className="kg-picker__name">{h.label ?? h.key}</span>
                <span className="kg-picker__meta">{h.thing} · {h.matched ?? h.key}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
