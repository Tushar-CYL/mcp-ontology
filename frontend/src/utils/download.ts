/** Browser-only helpers: file download and clipboard. */

export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/** The file name the server gave (Content-Disposition), else the fallback. */
export function fileName(contentDisposition: string | null, fallback: string): string {
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(contentDisposition ?? '')
  return m ? decodeURIComponent(m[1]) : fallback
}

/** An error answer in words a person can act on. */
export function downloadError(status: number, body: unknown): string {
  const msg = (body as { error?: { message?: string } } | null)?.error?.message
    ?? `the server answered ${status}`
  return /no route|older version/i.test(msg)
    ? 'The server is older than this page. Stop it (Ctrl+C) and start it again with python run_server.py, then try again.'
    : msg
}
