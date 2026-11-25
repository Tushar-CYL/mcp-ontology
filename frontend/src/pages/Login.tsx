import { useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { api, describeError } from '../api/client'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { readSession, writeSession } from '../session'

/**
 * The front door. Email and password, then the workspace the person already
 * has: their ontologies, graph, semantic layer and context. When this server
 * requires an access token, the password is that token.
 */
export function Login() {
  useDocumentTitle('Sign in')
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const next = params.get('next') || '/tools/ontology'
  const destination = next.startsWith('/') && !next.startsWith('//') ? next : '/tools/ontology'

  if (readSession()) return <Navigate to={destination} replace />

  const submit = async () => {
    if (!email.trim() || !password.trim()) return
    setBusy(true)
    setError(null)
    try {
      await api.login(password.trim())
      writeSession(email.trim())
      navigate(destination, { replace: true })
    } catch (e) {
      setError(describeError(e).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <form className="login__card" onSubmit={(e) => { e.preventDefault(); void submit() }}>
        <div className="login__brand">
          <span className="login__mark" aria-hidden="true" />
          Strata
        </div>
        <label className="login__field">
          Email
          <input className="login__input" type="email" autoComplete="username" required autoFocus
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="login__field">
          Password
          <input className="login__input" type="password" autoComplete="current-password" required
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error ? <p className="login__error" role="alert">{error}</p> : null}
        <button type="submit" className="login__submit" disabled={busy || !email.trim() || !password.trim()}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
