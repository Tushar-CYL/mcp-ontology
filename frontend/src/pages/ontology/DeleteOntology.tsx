import { useEffect, useRef, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { api, describeError } from '../../api/client'
import { Button } from '../../components/Button'
import { useToast } from '../../context/ToastContext'

/**
 * Delete an ontology, after a confirmation that says exactly what goes: the
 * ontology, its versions, notes and corrections are removed from the
 * database. The data sources it was built from stay.
 */
export function DeleteOntology({ id, name, onDeleted, compact = false }: {
  id: string
  name: string
  onDeleted: () => void
  compact?: boolean
}) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  const remove = async () => {
    setBusy(true)
    try {
      await api.ontoDelete(id)
      toast.push({ title: `Deleted “${name}”`, message: 'Removed from the database. Your data sources were not touched.',
        tone: 'success' })
      setOpen(false)
      onDeleted()
    } catch (e) {
      toast.push({ title: 'Not deleted', message: describeError(e).message, tone: 'error' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Button size="sm" variant="ghost" icon={<Trash2 size={14} />} onClick={() => setOpen(true)}
        aria-label={`Delete ${name}`}>
        {compact ? null : 'Delete'}
      </Button>
      <dialog ref={dialog} className="onto-dialog" onClose={() => setOpen(false)}
        aria-labelledby={`del-${id}`}>
        <h2 id={`del-${id}`}>Delete “{name}”?</h2>
        <p>This permanently removes the ontology from the database:</p>
        <ul>
          <li>its things, fields and links</li>
          <li>every published version (Nexus, Excel and agents stop seeing it)</li>
          <li>your notes and corrections</li>
        </ul>
        <p className="onto-dialog__keep">The data sources it was built from stay connected.</p>
        <div className="onto-dialog__actions">
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
          <Button variant="danger" icon={<Trash2 size={15} />} loading={busy} onClick={remove}>
            Delete ontology
          </Button>
        </div>
      </dialog>
    </>
  )
}
