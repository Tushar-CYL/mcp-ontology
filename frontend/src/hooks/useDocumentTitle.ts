import { useEffect } from 'react'

/** Set the document title for the current screen. */
export function useDocumentTitle(title?: string): void {
  useEffect(() => {
    document.title = title ? `${title} · Strata` : 'Strata'
  }, [title])
}
