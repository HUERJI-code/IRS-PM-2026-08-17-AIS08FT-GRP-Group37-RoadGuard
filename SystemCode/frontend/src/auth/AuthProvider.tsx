import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { createApiClient } from '../api/client'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { AuthContext } from './context'
import './auth.css'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Model<'SessionResponse'> | null>(null)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const version = useRef(0)
  const csrf = session?.csrf_token
  const invalidate = useCallback(() => { version.current++; setSession(null); setChecking(false) }, [])
  const check = useCallback(async () => {
    const generation = ++version.current
    try {
      const value = await createApiClient().session()
      if (version.current === generation) { setSession(value); setError('') }
    } catch (err) {
      if (version.current !== generation) return
      setSession(null)
      if (!(err instanceof ApiError && err.status === 401)) setError('Cannot connect to the service. Check the backend and retry.')
    } finally { if (version.current === generation) setChecking(false) }
  }, [])
  const cancelCheck = useCallback(() => { version.current++ }, [])
  useEffect(() => { if (!session) document.title = 'Sign in · RoadGuard' }, [session])
  useEffect(() => {
    let active = true
    void Promise.resolve().then(() => { if (active) void check() })
    const refresh = () => { if (document.visibilityState !== 'hidden') void check() }
    const changed = (event: StorageEvent) => { if (event.key === 'roadguard-auth-change') { setSession(null); setChecking(true); void check() } }
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', changed)
    return () => { active = false; cancelCheck(); window.removeEventListener('focus', refresh); window.removeEventListener('storage', changed) }
  }, [check, cancelCheck])
  useEffect(() => {
    if (!session) return
    const timer = setTimeout(invalidate, Math.max(0, session.expires_at * 1000 - Date.now()))
    return () => clearTimeout(timer)
  }, [session, invalidate])
  function notifyTabs() {
    // Only a change notification is stored; credentials and session tokens are never persisted here.
    try { localStorage.setItem('roadguard-auth-change', crypto.randomUUID()) } catch { /* Session still works without storage. */ }
  }
  async function login(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const generation = ++version.current
    setBusy(true); setError('')
    try {
      const value = await createApiClient().login(username.trim(), password)
      // A failed login can invalidate; a successful login must belong to this request.
      if (version.current === generation) { setSession(value); setPassword(''); notifyTabs() }
    } catch (err) {
      setPassword('')
      setError(err instanceof ApiError && err.status === 429 ? 'Too many attempts. Please try again later.' : err instanceof ApiError && err.status === 401 ? 'Incorrect username or password.' : 'Sign-in failed. Check the service connection and retry.')
    } finally { setBusy(false) }
  }
  async function logout() {
    // Keep the session visible on a network failure so logout is never falsely confirmed.
    await createApiClient(undefined, 8000, { csrfToken: () => csrf, onUnauthorized: invalidate }).logout()
    invalidate(); notifyTabs()
  }
  if (checking) return <div className="auth-loading" role="status">Checking your account…</div>
  if (session) return <AuthContext.Provider value={{ session, invalidate, logout }}><div key={`${session.user.user_id}:${session.user.role}:${session.user.crew_id}:${session.csrf_token}`}>{children}</div></AuthContext.Provider>
  return <main className="login-shell">
    <section className="login-intro"><a className="login-brand" href="/" aria-label="RoadGuard Home"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M8 25 13 7h6l5 18M12 18h8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" /><path d="M16 10v3m0 9v3" stroke="currentColor" strokeWidth="2" /></svg></span>RoadGuard</a><div><p className="eyebrow">JURONG EAST & WEST</p><h1>Every road defect,<br />every next step.</h1><p>From road inspection to field repairs, each role has a focused workspace.</p></div><span>Road maintenance collaboration · NUS-ISS</span></section>
    <section className="login-panel"><form onSubmit={(event) => void login(event)}><p className="eyebrow">WELCOME BACK</p><h2>Sign in to workspace</h2><p className="login-description">Use your assigned account to access your workspace.</p>
      <label htmlFor="login-username">Username</label><input id="login-username" name="username" autoComplete="username" required maxLength={32} value={username} disabled={busy} onChange={(event) => setUsername(event.target.value)} />
      <label htmlFor="login-password">Password</label><input id="login-password" name="password" type="password" autoComplete="current-password" required maxLength={256} value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} />
      {error && <p className="login-error" role="alert">{error}</p>}
      <button className="button login-submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in →'}</button>
      <div className="login-roles"><span>Inspector<small>Upload photos and view results</small></span><span>Crew<small>Crew routes and task completion</small></span><span>Central dispatcher<small>Review, task and route management</small></span></div>
      <p className="field-note">Accounts and crew assignments are managed by the administrator. Contact the project owner for access or a password reset.</p>
    </form></section>
  </main>
}
