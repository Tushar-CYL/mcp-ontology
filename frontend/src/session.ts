const KEY = 'strata-signed-in'

export type SignedIn = { email: string }

export function readSession(): SignedIn | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SignedIn
    return parsed.email ? parsed : null
  } catch {
    return null
  }
}

export function writeSession(email: string) {
  localStorage.setItem(KEY, JSON.stringify({ email }))
}

export function clearSession() {
  localStorage.removeItem(KEY)
}
