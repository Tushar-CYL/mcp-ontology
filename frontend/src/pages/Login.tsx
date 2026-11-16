import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { KeyRound } from 'lucide-react'
import { api, describeError } from '../api/client'
import { Button } from '../components/Button'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

/**
 * Sign in with the server's access token (STRATA_API_TOKENS). Shown only
 * when the server requires one; a laptop install never sees this page.
 */
export function Login() {
  useDocumentTitle('Sign in')
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const next = params.get('next') || '/tools/ontology'

  const submit = async () => {
    if (!token.trim()) return
    setBusy(true)
    setError(null)
    try {
      await api.login(token.trim())
      navigate(next.startsWith('/') ? next : '/tools/ontology', { replace: true })
    } catch (e) {
      setError(describeError(e).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <form className="login__card" onSubmit={(e) => { e.preventDefault(); void submit() }}>
        <span className="brand-mark" aria-hidden="true">S</span>
        <h1>Sign in to Strata</h1>
        <p>This server requires an access token. Ask the person who runs it, or find it in the server's <code>STRATA_API_TOKENS</code> setting.</p>
        <label className="field">
          <span className="field__label">Access token</span>
          <input className="input" type="password" autoComplete="current-password" value={token}
            onChange={(e) => setToken(e.target.value)} autoFocus />
        </label>
        {error ? <p className="login__error" role="alert">{error}</p> : null}
        <Button type="submit" variant="primary" icon={<KeyRound size={15} />} loading={busy} disabled={!token.trim()} fullWidth>
          Sign in
        </Button>
      </form>
    </main>
  )
}
