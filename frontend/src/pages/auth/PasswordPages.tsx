import { Mail } from 'lucide-react'
import { AuthShell } from '../../components/kit/AuthShell'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import PasswordInput from '../../components/PasswordInput'
import { Alert, EmptyState, fmtDate, useLoad } from '../../components/ui'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const r = await api<{ message: string }>('/auth/forgot-password', { body: { email } })
      setMsg(r.message)
    } catch (err) {
      setError((err as Error).message)
    }
  }
  return (
    <AuthShell>
      <div className="brand"><span className="brand-mark" aria-hidden="true">A</span>AI Tutor</div>
      <div className="card">
        <h1>Reset your password</h1>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="email">E-mail</label>
            <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <Alert>{error}</Alert>
          <Alert kind="success">{msg}</Alert>
          <button type="submit">Send reset link</button>
        </form>
        <p className="small"><Link to="/login">Back to sign in</Link></p>
      </div>
    </AuthShell>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [mismatch, setMismatch] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setMismatch(pw !== pw2)
    if (pw !== pw2) return
    setError('')
    try {
      await api('/auth/reset-password', { body: { token: params.get('token'), new_password: pw } })
      setDone(true)
    } catch (err) {
      setError((err as Error).message)
    }
  }
  return (
    <AuthShell>
      <div className="brand"><span className="brand-mark" aria-hidden="true">A</span>AI Tutor</div>
      <div className="card">
        <h1>Choose a new password</h1>
        {done ? (
          <Alert kind="success">Password changed. You can now <Link to="/login">sign in</Link>.</Alert>
        ) : (
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="pw">New password</label>
              <PasswordInput id="pw" autoComplete="new-password" required value={pw} onChange={(e) => setPw(e.target.value)} aria-describedby="pw-hint" />
              <p id="pw-hint" className="field-hint">At least 10 characters, with letters and digits.</p>
            </div>
            <div className="field">
              <label htmlFor="pw2">Repeat new password</label>
              <PasswordInput id="pw2" autoComplete="new-password" required value={pw2} onChange={(e) => setPw2(e.target.value)} aria-invalid={mismatch || undefined} aria-describedby={mismatch ? 'pw2-error' : undefined} />
              {mismatch && <p id="pw2-error" className="field-error" role="alert">Passwords do not match. Type the same password in both fields.</p>}
            </div>
            <Alert>{error}</Alert>
            <button type="submit">Save password</button>
          </form>
        )}
      </div>
    </AuthShell>
  )
}

type Mail = { to: string; subject: string; body: string; sent_at: string }

function linkify(text: string) {
  return text.split(/(https?:\/\/\S+)/g).map((part, i) =>
    part.startsWith('http') ? (
      <a key={i} href={part.replace(/^https?:\/\/[^/]+/, '')}>{part}</a>
    ) : (
      <span key={i}>{part}</span>
    ),
  )
}

export function DevOutboxPage() {
  const { data, error, reload } = useLoad(() => api<Mail[]>('/dev/outbox'))
  return (
    <AuthShell wide="wide">
      <div className="brand"><span className="brand-mark" aria-hidden="true">A</span>AI Tutor</div>
      <div className="spread">
        <h1>Demo mailbox</h1>
        <button className="secondary" onClick={reload}>Refresh</button>
      </div>
      <p className="muted small">No SMTP server is configured, so e-mails the app sends are shown here (development only).</p>
      <Alert>{error}</Alert>
      {data?.length === 0 && <EmptyState icon={Mail} title="No e-mails yet">E-mails the app sends (verification, password reset) will appear here.</EmptyState>}
      {data?.map((m, i) => (
        <div className="card" key={i}>
          <div className="spread"><strong>{m.subject}</strong><span className="small muted">{fmtDate(m.sent_at)}</span></div>
          <div className="small muted">To: {m.to}</div>
          <pre className="plain" tabIndex={0}>{linkify(m.body)}</pre>
        </div>
      ))}
      <p><Link to="/login">Back to sign in</Link></p>
    </AuthShell>
  )
}
