import { useState, type ReactNode } from 'react'
import { describeError } from '../api/client'
import { downloadError, fileName } from '../utils/download'

/**
 * A download that never saves an error as a file. A plain <a download> keeps
 * whatever comes back, so a server without the route left people with a
 * "bundle.json" holding an error message. This checks the answer first: a
 * file is saved under its real name, an error is said on the page.
 */
export function DownloadLink({ href, fallback, className, children }: {
  href: string
  fallback: string
  className?: string
  children: ReactNode
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const get = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(href, { credentials: 'same-origin' })
      if (!res.ok) {
        setError(downloadError(res.status, await res.json().catch(() => null)))
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName(res.headers.get('content-disposition'), fallback)
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 30_000)
    } catch (err) {
      setError(describeError(err).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <a href={href} className={className} onClick={(e) => void get(e)} aria-busy={busy}>
        {children}{busy ? <span className="dl-busy"> (preparing…)</span> : null}
      </a>
      {error ? <span className="dl-error" role="alert">{error}</span> : null}
    </>
  )
}
